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
    policy_version = "privacy-r9-semantic-identity-role"
    prompt_version = "privacy-plan-v13-no-identifier-escape"
    max_batch_codepoints = 800
    response_schema = {
        "name": "privacy_plan_batch", "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "entities": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "span_id": {"type": "string"},
                        "kind": {"type": "string", "enum": ["person", "contact", "role", "organization"]},
                        "expected_text": {"type": "string"},
                        "identity_hint": {"type": ["string", "null"]},
                    },
                    "required": ["span_id", "kind", "expected_text", "identity_hint"],
                    "additionalProperties": False,
                }},
            },
            "required": ["entities"],
            "additionalProperties": False,
        },
    }
    _personal_id = re.compile(r"(?<!\w)OP_ID\s*:?\s*[A-Za-z0-9-]+(?!\w)", re.I)
    _temporal = re.compile(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december|today|tomorrow|until|through|by)\b|\b\d{4}-\d{2}(?:-\d{2})?\b", re.I)

    def __init__(self, provider):
        self.provider = provider

    @staticmethod
    def _identity_variants(person):
        """Expose conservative name forms for semantic identity comparison."""
        display=(person.get("display_name") or "").strip()
        variants=[display, *[contact.get("value") for contact in person.get("contacts",[])]]
        parts=display.split()
        if len(parts)>=2 and all(part for part in parts):
            initials="".join(part[0].upper() for part in parts)
            variants.extend([initials, f"{parts[0][0].upper()}. {parts[-1]}",
                             f"{parts[0]} {parts[-1][0].upper()}."])
        return list(dict.fromkeys(value for value in variants if value))

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

    @classmethod
    def _model_text(cls, text, people):
        """Hide PII already covered by deterministic validation from the semantic model."""
        ranges=[]
        for pattern in (EMAIL,PHONE,cls._personal_id):
            ranges.extend((match.start(),match.end()) for match in pattern.finditer(text))
        merged=[]
        for start,end in sorted(ranges):
            if merged and start<=merged[-1][1]:
                merged[-1]=(merged[-1][0],max(merged[-1][1],end))
            else:
                merged.append((start,end))
        for start,end in reversed(merged):
            text=text[:start]+"[deterministically protected]"+text[end:]
        return text

    @staticmethod
    def _contains(ranges, span_id, start, end, kinds=None):
        return any(item.span_id==span_id and item.start<=start and item.end>=end and
                   (kinds is None or item.kind in kinds) for item in ranges)

    @staticmethod
    def _resolve_entity_offsets(result, spans):
        """Derive ranges from source text; discard entities with no source occurrence."""
        by_id={span["span_id"]:span["text"] for span in spans}
        resolved=[]
        for item in result.get("entities",[]):
            text=by_id.get(item.get("span_id"));expected=item.get("expected_text")
            matches=[match.start() for match in re.finditer(re.escape(expected),text)] if isinstance(text,str) and isinstance(expected,str) and expected else []
            if len(matches)!=1:
                candidates=[(span_id,value) for span_id,value in by_id.items() if isinstance(expected,str) and expected and value.count(expected)==1]
                if len(candidates)!=1:
                    continue
                item["span_id"],text=candidates[0]
                matches=[match.start() for match in re.finditer(re.escape(expected),text)]
            item.pop("start",None);item.pop("end",None)
            item["start"]=matches[0];item["end"]=matches[0]+len(expected)
            item["evidence_span_ids"]=[item["span_id"]]
            if item.get("kind")=="person" and not item.get("identity_hint"):
                item["identity_hint"]="NEW_"+hashlib.sha256(expected.casefold().encode()).hexdigest()[:12]
            elif item.get("kind")!="person":
                item["identity_hint"]=None
            item["confidence"]="certain"
            resolved.append(item)
        result["entities"]=resolved
        return result

    @classmethod
    def _filter_model_entities(cls, result):
        """Reject semantic labels whose source text cannot have the claimed PII shape."""
        blocked_name_parts={
            "account", "category", "customer", "data", "delivery", "director", "executive",
            "gmbh", "lead", "manager", "officer", "org", "project", "protection", "relex",
            "report", "solution", "subject", "team", "technical",
        }

        def looks_like_person(value):
            parts=value.split()
            if not 1<=len(parts)<=4 or any(part.casefold() in blocked_name_parts for part in parts):
                return False
            return all((re.fullmatch(r"[A-Z]\.",part) is not None) or
                       (part[0].isupper() and all(char.isalpha() or char in "-'" for char in part))
                       for part in parts if part)

        def looks_like_address(value):
            lowered=value.casefold()
            address_terms=("street", "road", "avenue", "lane", "drive", "strasse", "straße", "ring", " rua ")
            return any(char.isdigit() for char in value) and (
                any(term in " "+lowered+" " for term in address_terms) or
                bool(re.search(r"\b\d{4,6}\b",value) and "," in value)
            )

        accepted=[]
        for entity in result.get("entities",[]):
            value=entity.get("expected_text","")
            kind=entity.get("kind")
            if kind=="person" and looks_like_person(value):
                accepted.append(entity)
            elif kind=="contact" and (EMAIL.fullmatch(value) or PHONE.fullmatch(value) or looks_like_address(value)):
                accepted.append(entity)
            elif kind=="personal_identifier" and cls._personal_id.fullmatch(value):
                accepted.append(entity)
        result["entities"]=accepted
        return result

    @classmethod
    def _enforce_deterministic_entities(cls, result, spans):
        by_id={span["span_id"]:span["text"] for span in spans}
        candidates=[]
        for span_id,text in by_id.items():
            for pattern,kind in ((EMAIL,"personal_identifier"),(PHONE,"contact"),(cls._personal_id,"personal_identifier")):
                for match in pattern.finditer(text):
                    candidates.append((span_id,match.start(),match.end(),match.group(),kind))
        entities=result.setdefault("entities",[])
        for span_id,start,end,expected,kind in candidates:
            entity=next((item for item in entities
                         if item.get("span_id")==span_id and item.get("start",-1)<=start
                         and item.get("end",-1)>=end),None)
            if entity is None:
                entities.append({"span_id":span_id,"start":start,"end":end,
                    "kind":kind,"identity_hint":None,"evidence_span_ids":[span_id],
                    "expected_text":expected,"confidence":"certain"})
            else:
                entity.update(start=start,end=end,kind=kind,expected_text=expected,
                              confidence="certain")
        return result

    @staticmethod
    def _enforce_known_people(result, spans, people):
        entities=result.setdefault("entities",[])
        for person_id,person in (people or {}).items():
            if person.get("state")=="erased":
                continue
            for alias in [person.get("display_name"), *[value.get("value") for value in person.get("contacts",[])]]:
                if not alias:
                    continue
                pattern=re.compile(r"(?<!\w)"+re.escape(alias)+r"(?!\w)",re.I)
                for span in spans:
                    for match in pattern.finditer(span["text"]):
                        entities.append({"span_id":span["span_id"],"start":match.start(),"end":match.end(),
                            "kind":"person","identity_hint":person_id,"evidence_span_ids":[span["span_id"]],
                            "expected_text":match.group(),"confidence":"certain"})
        return result

    @staticmethod
    def _make_protective_entities_certain(result):
        for entity in result.get("entities",[]):
            if entity.get("kind") in {"contact","personal_identifier"}:
                entity["confidence"]="certain"
        return result

    @staticmethod
    def _dedupe_entities(result):
        unique={}
        for entity in result.get("entities",[]):
            key=(entity.get("span_id"),entity.get("start"),entity.get("end"),entity.get("expected_text"))
            prior=unique.get(key)
            if prior is None or (prior.get("confidence")!="certain" and entity.get("confidence")=="certain"):
                unique[key]=entity
        result["entities"]=list(unique.values())
        return result

    @staticmethod
    def _bind_known_identities(entities, people):
        aliases={}
        first_names={}
        for person_id, person in (people or {}).items():
            if person.get("state")=="erased":
                continue
            display_name=person.get("display_name")
            for alias in [display_name, *[contact.get("value") for contact in person.get("contacts",[])]]:
                if alias:
                    aliases.setdefault(alias.casefold(),set()).add(person_id)
            if display_name and len(display_name.split())>1:
                first_names.setdefault(display_name.split()[0].casefold(),set()).add(person_id)
        for entity in entities:
            if entity.get("kind")=="person":
                value=entity.get("expected_text","").casefold()
                matches=aliases.get(value,set()) or first_names.get(value,set())
                if len(matches)==1:
                    entity["identity_hint"]=next(iter(matches))
                    entity["confidence"]="certain"
        return entities

    @staticmethod
    def _compile_edits(entities, resolutions=()):
        """Compile source-bound edits from validated semantic entity decisions."""
        edits=[]
        exempt={(value.get("span_id"),value.get("start"),value.get("end"),value.get("expected_text"))
                for value in resolutions if value.get("decision")=="system_code"}
        for entity in entities:
            if (entity.span_id,entity.start,entity.end,entity.expected_text) in exempt:
                continue
            if entity.confidence!="certain":
                continue
            if entity.kind=="person":
                if entity.identity_hint:
                    reason,replacement="identity",entity.identity_hint
                else:
                    continue
            elif entity.kind=="contact":
                reason,replacement="contact","[contact removed]"
            elif entity.kind=="personal_identifier":
                reason,replacement="personal_identifier","[personal identifier removed]"
            else:
                continue
            edits.append(PrivacyEdit(span_id=entity.span_id,start=entity.start,end=entity.end,
                expected_text=entity.expected_text,replacement=replacement,reason=reason))
        return edits

    def _validate_batch(self, result, spans, resolutions=(), people=None):
        variant_owners={}
        for person_id,person in (people or {}).items():
            for variant in self._identity_variants(person):
                variant_owners.setdefault(variant.casefold(),set()).add(person_id)
        for entity in result.get("entities",[]):
            hint=entity.get("identity_hint")
            if entity.get("kind")!="person" and hint is not None:
                raise ValueError("non_person_identity_hint")
            owners=variant_owners.get(str(entity.get("expected_text","")).casefold(),set())
            if len(owners)==1 and (entity.get("kind")!="person" or hint!=next(iter(owners))):
                raise ValueError("known_name_variant_misclassified")
        result=self._resolve_entity_offsets(result,spans)
        for entity in result.get("entities",[]):
            hint=entity.get("identity_hint")
            if hint and hint not in (people or {}) and not hint.startswith("NEW_"):
                raise ValueError("unknown_identity_hint")
        result=self._filter_model_entities(result)
        result=self._enforce_deterministic_entities(result,spans)
        result=self._enforce_known_people(result,spans,people)
        result=self._make_protective_entities_certain(result)
        result=self._dedupe_entities(result)
        by_id={span["span_id"]:span for span in spans}
        entities_raw=self._bind_known_identities(result.get("entities",[]),people)
        entities=[PrivacyEntity.model_validate(value) for value in entities_raw]
        edits=self._compile_edits(entities,resolutions)
        reasons=[]
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
            expected={"identity":{"person"},"contact":{"contact"},
                      "personal_identifier":{"personal_identifier"},"contextual_risk":{"uncertain"}}[edit.reason]
            if not self._contains(entities,edit.span_id,edit.start,edit.end,expected):raise ValueError("unsupported_edit")
            if edit.reason=="contextual_risk":raise ValueError("risk_must_not_rewrite")
            if edit.replacement==edit.expected_text:raise ValueError("non_transforming_edit")
        resolution_map={(value["span_id"],value["start"],value["end"],value["expected_text"]):value
                        for value in resolutions}
        edit_map={(value.span_id,value.start,value.end,value.expected_text):value for value in edits}
        for entity in entities:
            key=(entity.span_id,entity.start,entity.end,entity.expected_text)
            resolution=resolution_map.get(key)
            edit=edit_map.get(key)
            if entity.kind in {"person","contact","personal_identifier"}:
                permitted_non_edit=(entity.confidence=="uncertain" and bool(reasons) or
                                    resolution and resolution["decision"]=="system_code" and
                                    entity.kind=="personal_identifier")
                expected_reason={"person":"identity","contact":"contact",
                                 "personal_identifier":"personal_identifier"}[entity.kind]
                if not permitted_non_edit and (edit is None or edit.reason!=expected_reason):
                    raise ValueError("protected_entity_without_edit")
        decision_contract={
            "system_code":("personal_identifier",None), "contact":("contact","contact"),
            "personal_identifier":("personal_identifier","personal_identifier"),
        }
        for key,resolution in resolution_map.items():
            entity=next((value for value in entities if
                         (value.span_id,value.start,value.end,value.expected_text)==key),None)
            if entity is None:raise ValueError("resolution_not_applied")
            decision=resolution["decision"]
            if decision.startswith("bind:"):
                if entity.kind!="person" or entity.identity_hint!=decision[5:] or edit_map.get(key) is None or edit_map[key].reason!="identity":
                    raise ValueError("invalid_binding_resolution")
            else:
                expected_kind,expected_edit=decision_contract[decision]
                if entity.kind!=expected_kind:raise ValueError("invalid_classification_resolution")
                if expected_edit is None and edit_map.get(key) is not None:raise ValueError("non_edit_resolution_rewritten")
                if expected_edit is not None and (edit_map.get(key) is None or edit_map[key].reason!=expected_edit):
                    raise ValueError("resolved_entity_without_edit")
        for span in spans:
            text=span["text"]
            for pattern,kinds in ((EMAIL,{"personal_identifier"}),(PHONE,{"contact"}),(self._personal_id,{"personal_identifier"})):
                for match in pattern.finditer(text):
                    if not self._contains(entities,span["span_id"],match.start(),match.end(),kinds):
                        raise ValueError("deterministic_candidate_missed")
        return entities,edits,reasons

    @staticmethod
    def _validate_resolutions(record_id,record_version,source_hash,spans,resolutions,people):
        by_id={span["span_id"]:span["text"] for span in spans}
        allowed={"system_code","contact","personal_identifier"}
        validated=[]
        for value in resolutions or []:
            decision=value.get("decision","")
            if (value.get("record_id")!=record_id or value.get("record_version")!=record_version or
                    value.get("source_hash")!=source_hash or value.get("span_id") not in by_id):
                raise DomainError("privacy_unresolved")
            start=value.get("start");end=value.get("end");expected=value.get("expected_text")
            if (type(start) is not int or type(end) is not int or start<0 or end<=start or
                    by_id[value["span_id"]][start:end]!=expected):
                raise DomainError("privacy_unresolved")
            if decision.startswith("bind:"):
                if decision[5:] not in (people or {}):raise DomainError("privacy_unresolved")
            elif decision not in allowed:raise DomainError("privacy_unresolved")
            validated.append({key:value[key] for key in (
                "diagnostic_id","record_id","record_version","source_hash","span_id","start","end",
                "expected_text","kind","reason","decision")})
        return validated

    async def _generate(self, payload, prior=None, error=None):
        system=(
            "Find personal information in every supplied span. Return one JSON object containing only entities. "
            "For each entity return span_id, expected_text copied verbatim from that span, kind, and identity_hint. "
            "Kinds are person, contact, role, and organization. Exact personal identifiers are handled separately "
            "by the application and are not a semantic kind. Contact includes postal addresses. Classify job titles, responsibilities, offices, departments, honorifics, and "
            "organization-plus-title labels as role or organization, never person. Return those non-person labels "
            "so the application can verify that the distinction was made. "
            "For a person, compare spelling variants, shortened names, initials, and transcription variants against "
            "the aliases and derived name_variants in known_identities. If source text exactly matches a name_variant "
            "belonging to exactly one identity, classify it as person and use that identity ID. For other person "
            "variants, set identity_hint to a supplied ID only when the "
            "reference is unambiguous and context supports it; otherwise null. For every non-person kind, "
            "identity_hint must be null. "
            "When PII is ambiguous, use personal_identifier. Do not emit organizations, roles, dates, business status, "
            "private circumstances, warnings, or ordinary prose. Never invent source text. The application owns offsets, "
            "coverage, identity binding, confidence, and edits."
        )
        request=dict(payload)
        if prior is not None:
            request["rejected_output"]=prior
            request["validation_error"]=error
            request["instruction"]="Correct the rejected output once; do not change or omit source coverage."
        try:
            return await self.provider.generate("privacy",system,request,max_tokens=2048,
                                                json_schema=self.response_schema,temperature=0)
        except Exception:
            raise DomainError("provider_unavailable") from None

    async def plan(self,project_id,record_id,record_version,spans,source_hash,people=None,resolutions=None,identity_revision=0):
        source_spans=[span for span in spans if not span["span_id"].startswith("title:")]
        if hashlib.sha256("\n".join(span["text"] for span in source_spans).encode()).hexdigest()!=source_hash:
            raise DomainError("privacy_unresolved")
        resolutions=self._validate_resolutions(record_id,record_version,source_hash,spans,resolutions,people)
        batches=self._batches(spans);all_entities=[];all_edits=[];all_reasons=[];covered=[];hashes=[];corrections=0
        known=[{"id":pid,"aliases":[person["display_name"],*[contact["value"] for contact in person.get("contacts",[])]],
                "name_variants":self._identity_variants(person)}
               for pid,person in sorted((people or {}).items())]
        for index,batch in enumerate(batches):
            batch_ids={span["span_id"] for span in batch}
            batch_resolutions=[value for value in resolutions if value["span_id"] in batch_ids]
            payload={"record_id":record_id,"record_version":record_version,"source_hash":source_hash,
                     "batch_index":index,"batch_count":len(batches),"known_identities":known,
                     "admin_resolutions":batch_resolutions,
                     "previous_context":spans[spans.index(batch[0])-1]["text"][-500:] if spans.index(batch[0]) else None,
                     "next_context":spans[spans.index(batch[-1])+1]["text"][:500] if spans.index(batch[-1])+1<len(spans) else None,
                     "spans":[{"span_id":span["span_id"],"text":self._model_text(span["text"],people)} for span in batch]}
            hashes.append(hashlib.sha256(json.dumps(payload["spans"],ensure_ascii=False,sort_keys=True).encode()).hexdigest())
            result=await self._generate(payload)
            for attempt in range(4):
                try:
                    entities,edits,reasons=self._validate_batch(result,batch,batch_resolutions,people)
                    break
                except Exception as exc:
                    if attempt == 3:
                        raise DomainError("privacy_unresolved") from None
                    corrections+=1
                    result=await self._generate(payload,result,str(exc))
            reasons=[]
            all_entities.extend(entities);all_edits.extend(edits);all_reasons.extend(reasons)
            covered.extend(span["span_id"] for span in batch)
        model=getattr(getattr(self.provider,"settings",None),"model",None) or "configured-model"
        plan_seed=f"{project_id}:{record_id}:{record_version}:{source_hash}:{self.policy_version}:{self.prompt_version}"
        return PrivacyPlan(plan_id=str(__import__("uuid").uuid5(__import__("uuid").NAMESPACE_URL,plan_seed)),
            project_id=project_id,record_id=record_id,record_version=record_version,source_hash=source_hash,
            policy_version=self.policy_version,prompt_version=self.prompt_version,model_version=model,
            identity_revision=identity_revision,
            batch_hashes=hashes,corrections_used=corrections,entities=all_entities,edits=all_edits,
            covered_span_ids=covered,unresolved_reasons=sorted(set(all_reasons)),complete=len(covered)==len(spans))


def validate_sanitized(plan, sanitized_by_id, resolutions=()):
    """Reject direct identifiers that survived the application-owned edit map."""
    edits={(value["span_id"],value["start"],value["end"],value["expected_text"]):value
           for value in plan["edits"]}
    exemptions={};exempt_entities=set()
    entities={(value["span_id"],value["start"],value["end"],value["expected_text"]):value
              for value in plan["entities"]}
    for resolution in resolutions:
        key=(resolution.get("span_id"),resolution.get("start"),resolution.get("end"),
             resolution.get("expected_text"))
        entity=entities.get(key)
        if (resolution.get("decision")!="system_code" or
                resolution.get("record_id")!=plan["record_id"] or
                resolution.get("record_version")!=plan["record_version"] or
                resolution.get("source_hash")!=plan["source_hash"] or
                not entity or entity["kind"]!="personal_identifier"):
            continue
        shift=sum(len(edit["replacement"])-(edit["end"]-edit["start"])
                  for edit in plan["edits"] if edit["span_id"]==key[0] and edit["end"]<=key[1])
        final_key=(key[1]+shift,key[2]+shift,key[3])
        text=sanitized_by_id.get(key[0],"")
        if text[final_key[0]:final_key[1]]==final_key[2]:
            exemptions.setdefault(key[0],set()).add(final_key)
            exempt_entities.add(key)
    for entity in plan["entities"]:
        if entity["kind"] not in ("person","contact","personal_identifier") or entity["confidence"]=="uncertain":
            continue
        key=(entity["span_id"],entity["start"],entity["end"],entity["expected_text"])
        if entity["kind"]=="personal_identifier" and key in exempt_entities:
            continue
        edit=edits.get(key)
        if edit is None:raise ValueError("protected_entity_without_edit")
        text=sanitized_by_id[entity["span_id"]]
        start=edit.get("sanitized_start");end=edit.get("sanitized_end")
        if type(start) is not int or type(end) is not int or text[start:end]!=edit["replacement"] or edit["replacement"]==edit["expected_text"]:
            raise ValueError("sanitized_mapping_mismatch")
    for span_id,text in sanitized_by_id.items():
        if EMAIL.search(text) or PHONE.search(text):raise ValueError("direct_identifier_survived")
        for match in PrivacyAgent._personal_id.finditer(text):
            if (match.start(),match.end(),match.group()) not in exemptions.get(span_id,set()):
                raise ValueError("direct_identifier_survived")
