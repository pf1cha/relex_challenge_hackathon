"""Restricted identity resolution; never guesses between same-name people."""
import re, hashlib, json
from ..contracts.errors import DomainError
from ..contracts.models import PrivacyPlan, PrivacyEntity, PrivacyEdit
from ..contracts.models import NormalizedText
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\w)\+\d[\d ()-]{7,}\d")
NAME = re.compile(r"\b[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?(?: [A-Z][a-z]+){1,3}\b")
PRIVATE = re.compile(r"\b(?:for|because of|due to) (?:surgery|divorce|medical treatment|a medical condition)\b", re.I)
ADDRESS = re.compile(r"\b\d{1,5}\s+[A-Z][\w ]{1,45}\s(?:Street|Road|Avenue|Lane|Drive)\b",re.I)

def aliases(person):
    return [person["display_name"], *[x["value"] for x in person["contacts"]]]

def normalize(text, people, *, ingestion=False):
    replacements=[]; ambiguous=False; ids=set()
    # Contacts identify a person in the local segment; a shared bare name alone does not.
    for person_id, person in people.items():
        if person.get("state") == "erased": continue
        for alias in aliases(person):
            if not alias: continue
            matches=list(re.finditer(r"(?<!\w)"+re.escape(alias)+r"(?!\w)",text,re.I))
            competitors=[pid for pid,p in people.items() if pid != person_id and alias.casefold() in [a.casefold() for a in aliases(p)]]
            for match in matches:
                chosen=person_id
                if competitors:
                    start=text.rfind("\n",0,match.start())+1
                    end=text.find("\n",match.end());end=len(text) if end<0 else end
                    local=text[start:end]
                    supported=[pid for pid in [person_id,*competitors] if any(c["value"].casefold() in local.casefold() for c in people[pid]["contacts"])]
                    if len(supported)!=1:
                        ambiguous=True;replacements.append((match.start(),match.end(),"[ambiguous person]"));continue
                    chosen=supported[0]
                ids.add(chosen);replacements.append((match.start(),match.end(),chosen))
    occupied=[]
    for start,end,value in sorted(set(replacements),key=lambda x:(x[0],-(x[1]-x[0]))):
        if not occupied or start>=occupied[-1][1]: occupied.append((start,end,value))
    result=text
    for start,end,value in reversed(occupied): result=result[:start]+value+result[end:]
    # Unmapped contacts must never leave preprocessing.
    result=EMAIL.sub("[unresolved contact]",result)
    result=PHONE.sub("[unresolved contact]",result)
    if "[unresolved contact]" in result: ambiguous=True
    result=ADDRESS.sub("[private address removed]",result)
    result=PRIVATE.sub("[private context removed]",result)
    # Unknown identities in object/owner positions cannot reach downstream models.
    if ingestion:
        role_name = re.search(r"\b(?:owner|assignee|contact|lead|manager|responsible person)\s*(?::|is|was|=)\s*([A-Z][a-z]+(?: [A-Z][a-z]+){0,3})\b", result)
        attributed_name = re.search(r"\b(?:assigned to|owned by|approved by|agreed by|contact|ask|with)\s+([A-Z][a-z]+(?: [A-Z][a-z]+){0,3})\b", result)
        if role_name or attributed_name: ambiguous=True
        # Multiword unresolved names are uncertain even when they are neither a
        # speaker nor the subject of a fixed verb (for example "chosen: Alice Example").
        # Explicit organization suffixes do not create person associations.
        for candidate in NAME.finditer(result):
            words=candidate.group().split()
            if words[0] not in {"The","This","That","New","Date","Subject","Title","Meeting","Report"} and words[-1] not in {"Inc","Ltd","Corporation","Company","University"}:
                ambiguous=True
    # Unknown speaker names and personal header identities quarantine input.
    if ingestion:
        if re.search(r"\b(?!The\b|This\b|That\b|Everyone\b|We\b)([A-Z][a-z]+(?: [A-Z][a-z]+){0,3}) (?=agreed|proposed|suggested|owns|confirmed|accepted|said|will lead|is responsible)",result): ambiguous=True
        for line in result.splitlines():
            head=re.match(r"^(?:From:|To:|Cc:|Speaker:)\s*(.+)",line,re.I)
            speaker=re.match(r"^([A-Z][a-z]+(?: [A-Z][a-z]+){0,3})(?:\s*\([^)]*\))?:",line)
            if (head and re.search(r"[A-Za-z]",head[1]) and not head[1].startswith(("PERSON_","[deleted user]"))) or speaker and not line.startswith(("From:","To:","Cc:","Speaker:","Date:","Subject:","Title:","Meeting:","Time:","Report:")):
                ambiguous=True
    return NormalizedText(text=result,person_ids=sorted(ids),ambiguous=ambiguous)

def erase_values(value, person):
    """Only unambiguous restricted copies use aliases; canonical copies use opaque ID."""
    replacements=[person["id"]]
    def walk(v):
        if isinstance(v,str):
            for old in replacements:v=v.replace(old,"[deleted user]")
            return v
        if isinstance(v,list):return [walk(x) for x in v]
        if isinstance(v,dict):return {k:walk(x) for k,x in v.items()}
        return v
    return walk(value)


def person_occurs(record, person_id, people):
    """Resolve restricted aliases per source segment without merging shared names."""
    texts=[record.get("title", "")]
    texts += [span["text"] for span in record.get("spans", [])]
    texts += [span["text"] for span in record.get("raw_spans", [])]
    for text in texts:
        resolved=normalize(text, people)
        if person_id in text or person_id in resolved.person_ids:
            return True
        person=people[person_id]
        if resolved.ambiguous and any(re.search(r"(?<!\w)"+re.escape(alias)+r"(?!\w)",text,re.I) for alias in aliases(person) if alias):
            return True
    return person_id in record.get("person_ids", [])


class PrivacyAgent:
    """Mandatory bounded semantic classification with deterministic validation."""
    policy_version = "privacy-r3"
    prompt_version = "privacy-plan-v2"
    max_batch_codepoints = 24000
    _personal_id = re.compile(r"(?<!\w)OP_ID\s*:?\s*[A-Za-z0-9-]+(?!\w)", re.I)
    _temporal = re.compile(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december|today|tomorrow|until|through|by)\b|\b\d{4}-\d{2}(?:-\d{2})?\b", re.I)

    def __init__(self, provider):
        self.provider = provider

    def _batches(self, spans):
        batches=[];current=[];size=0
        for span in spans:
            length=len(span["text"])
            if length > self.max_batch_codepoints:
                raise DomainError("privacy_unresolved")
            if current and size + length > self.max_batch_codepoints:
                batches.append(current);current=[];size=0
            current.append(span);size += length
        if current:batches.append(current)
        return batches

    @staticmethod
    def _contains(ranges, span_id, start, end, kinds=None):
        return any(item.span_id==span_id and item.start<=start and item.end>=end and
                   (kinds is None or item.kind in kinds) for item in ranges)

    def _validate_batch(self, result, spans):
        by_id={span["span_id"]:span for span in spans}
        if result.get("complete") is not True or set(result.get("covered_span_ids",[])) != set(by_id):
            raise ValueError("incomplete_coverage")
        entities=[PrivacyEntity.model_validate(value) for value in result.get("entities",[])]
        edits=[PrivacyEdit.model_validate(value) for value in result.get("edits",[])]
        occupied={}
        for item in [*entities,*edits]:
            span=by_id.get(item.span_id)
            if span is None or item.start < 0 or item.end <= item.start or item.end > len(span["text"]):
                raise ValueError("invalid_range")
            if span["text"][item.start:item.end] != item.expected_text:
                raise ValueError("source_mismatch")
        for entity in entities:
            if not set(entity.evidence_span_ids)<=set(by_id):raise ValueError("invalid_evidence")
        for edit in sorted(edits,key=lambda value:(value.span_id,value.start,value.end)):
            if edit.span_id in occupied and edit.start < occupied[edit.span_id]:raise ValueError("overlapping_edits")
            occupied[edit.span_id]=edit.end
            expected={"identity":{"person"},"contact":{"contact"},"private_cause":{"contextual_circumstance"},
                      "personal_identifier":{"personal_identifier"},"contextual_risk":{"uncertain"}}[edit.reason]
            if not self._contains(entities,edit.span_id,edit.start,edit.end,expected):raise ValueError("unsupported_edit")
            if edit.reason=="private_cause" and self._temporal.search(edit.expected_text):raise ValueError("operational_time_removed")
            if edit.reason=="contextual_risk":raise ValueError("risk_must_not_rewrite")
        for span in spans:
            text=span["text"]
            for pattern,kinds in ((EMAIL,{"contact"}),(PHONE,{"contact"}),(self._personal_id,{"personal_identifier"})):
                for match in pattern.finditer(text):
                    if not self._contains(entities,span["span_id"],match.start(),match.end(),kinds):
                        raise ValueError("deterministic_candidate_missed")
        reasons=result.get("unresolved_reasons",[])
        if not isinstance(reasons,list) or any(not isinstance(value,str) or not value or len(value)>500 for value in reasons):
            raise ValueError("invalid_unresolved_reason")
        return entities,edits,reasons

    async def _generate(self, payload, prior=None, error=None):
        system=(
            "You are the mandatory privacy classifier. Inspect every supplied span, including clean-looking spans. "
            "Return one JSON object with complete=true, covered_span_ids, entities, edits, and unresolved_reasons. "
            "Every entity/edit must use Python Unicode code-point start/end offsets and exact expected_text. Entity kinds: "
            "person, organization, role, contact, personal_identifier, contextual_circumstance, uncertain. "
            "Use evidence_span_ids and a record-local NEW_* identity_hint for supported new people; use a supplied PERSON_* only "
            "when evidence supports that binding. Keep organizations and roles distinct from people. Flag singling-out context without "
            "generalizing it. An edit may remove only a private cause, never an operational date/location/role, and must not invent prose. "
            "Edit reasons: identity, contact, private_cause, personal_identifier. Uncertainty must remain unresolved."
        )
        request=dict(payload)
        if prior is not None:
            request["rejected_output"]=prior
            request["validation_error"]=error
            request["instruction"]="Correct the rejected output once; do not change or omit source coverage."
        try:
            return await self.provider.generate("privacy",system,request,max_tokens=8192)
        except Exception:
            raise DomainError("provider_unavailable") from None

    async def plan(self,project_id,record_id,record_version,spans,source_hash,people=None,resolutions=None,identity_revision=0):
        source_spans=[span for span in spans if not span["span_id"].startswith("title:")]
        if hashlib.sha256("\n".join(span["text"] for span in source_spans).encode()).hexdigest()!=source_hash:
            raise DomainError("privacy_unresolved")
        batches=self._batches(spans);all_entities=[];all_edits=[];all_reasons=[];covered=[];hashes=[];corrections=0
        known=[{"id":pid,"aliases":[person["display_name"],*[contact["value"] for contact in person.get("contacts",[])]]}
               for pid,person in sorted((people or {}).items())]
        for index,batch in enumerate(batches):
            payload={"record_id":record_id,"record_version":record_version,"source_hash":source_hash,
                     "batch_index":index,"batch_count":len(batches),"known_identities":known,
                     "admin_resolutions":resolutions or [],
                     "previous_context":spans[spans.index(batch[0])-1]["text"][-500:] if spans.index(batch[0]) else None,
                     "next_context":spans[spans.index(batch[-1])+1]["text"][:500] if spans.index(batch[-1])+1<len(spans) else None,
                     "spans":[{"span_id":span["span_id"],"text":span["text"]} for span in batch]}
            hashes.append(hashlib.sha256(json.dumps(payload["spans"],ensure_ascii=False,sort_keys=True).encode()).hexdigest())
            result=await self._generate(payload)
            try:
                entities,edits,reasons=self._validate_batch(result,batch)
            except Exception as exc:
                corrections+=1
                result=await self._generate(payload,result,str(exc))
                try:entities,edits,reasons=self._validate_batch(result,batch)
                except Exception:raise DomainError("privacy_unresolved") from None
            all_entities.extend(entities);all_edits.extend(edits);all_reasons.extend(reasons)
            covered.extend(result["covered_span_ids"])
        model=getattr(getattr(self.provider,"settings",None),"model",None) or "configured-model"
        plan_seed=f"{project_id}:{record_id}:{record_version}:{source_hash}:{self.policy_version}:{self.prompt_version}"
        return PrivacyPlan(plan_id=str(__import__("uuid").uuid5(__import__("uuid").NAMESPACE_URL,plan_seed)),
            project_id=project_id,record_id=record_id,record_version=record_version,source_hash=source_hash,
            policy_version=self.policy_version,prompt_version=self.prompt_version,model_version=model,
            identity_revision=identity_revision,
            batch_hashes=hashes,corrections_used=corrections,entities=all_entities,edits=all_edits,
            covered_span_ids=covered,unresolved_reasons=sorted(set(all_reasons)),complete=len(covered)==len(spans))
