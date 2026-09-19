"""Restricted identity resolution; never guesses between same-name people."""
import re, hashlib
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
    """Mandatory record-level semantic privacy stage backed by the configured model."""
    policy_version = "privacy-r3"
    prompt_version = "privacy-plan-v1"
    def __init__(self, provider):
        self.provider = provider
    async def plan(self, project_id, record_id, record_version, spans, source_hash):
        payload = {"record_id": record_id, "record_version": record_version,
                   "source_hash": source_hash,
                   "spans": [{"span_id": s["span_id"], "text": s["text"]} for s in spans]}
        try:
            result = await self.provider.generate("privacy",
            "Classify every span. Return JSON with entities, edits, covered_span_ids, unresolved_reasons. "
            "Use only source-bound ranges; preserve operational facts and uncertainty. Never invent dates.",
                payload, max_tokens=8192)
        except Exception:
            raise DomainError("provider_unavailable") from None
        try:
            plan = PrivacyPlan(plan_id=str(__import__("uuid").uuid4()), project_id=project_id,
                record_id=record_id, record_version=record_version, source_hash=source_hash,
                policy_version=self.policy_version, prompt_version=self.prompt_version,
                entities=[PrivacyEntity.model_validate(x) for x in result.get("entities", [])],
                edits=[PrivacyEdit.model_validate(x) for x in result.get("edits", [])],
                covered_span_ids=list(result.get("covered_span_ids", [])),
                unresolved_reasons=list(result.get("unresolved_reasons", [])),
                complete=bool(result.get("complete", False)))
        except Exception:
            raise DomainError("provider_unavailable") from None
        by_id={s["span_id"]:s for s in spans}
        if set(plan.covered_span_ids) != set(by_id) or not plan.complete:
            raise DomainError("privacy_unresolved")
        occupied={}
        for edit in sorted(plan.edits, key=lambda x:(x.span_id,x.start,x.end)):
            span=by_id.get(edit.span_id)
            if not span or edit.start < 0 or edit.end <= edit.start or edit.end > len(span["text"]):
                raise DomainError("privacy_unresolved")
            if edit.span_id in occupied and edit.start < occupied[edit.span_id]:
                raise DomainError("privacy_unresolved")
            occupied[edit.span_id]=edit.end
        for entity in plan.entities:
            span=by_id.get(entity.span_id)
            if not span or entity.start < 0 or entity.end <= entity.start or entity.end > len(span["text"]):
                raise DomainError("privacy_unresolved")
        return plan
