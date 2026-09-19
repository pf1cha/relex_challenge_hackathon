"""Durable fenced jobs and external-write ledger. Network work is outside SQL locks."""
from __future__ import annotations
import asyncio, json, secrets, hashlib
from datetime import timedelta, datetime
from psycopg.types.json import Jsonb
from ..contracts.models import *
from ..contracts.errors import DomainError
from ..contracts.hashing import compact, artifact_key
from .service import now,iso,uid,dump,require
from .parsing import parse
from .privacy import normalize, person_occurs, validate_sanitized


def _proposed_person_id(plan_id, hint, value, aliases, batch_ids):
    """Reuse an identity proposal across records parsed from the same upload."""
    if hint in batch_ids:
        return batch_ids[hint]
    if aliases.get(value.casefold()):
        return None
    person_id="PERSON_"+hashlib.sha256((plan_id+":"+hint).encode()).hexdigest()[:16]
    batch_ids[hint]=person_id
    return person_id

SEQUENCES={
"ingest":["received","parsed","privacy_ready","extracted","indexed","published"],
"activate":["received","rebuilding","indexed","published"],
"deactivate":["invalidating","rebuilding","verifying","done"],
"delete_document":["invalidating","inventory","draining","sanitizing","rebuilding","removing_index","verifying","done"],
"erase_person":["invalidating","inventory","draining","sanitizing","rebuilding","removing_index","verifying","done"],
"rebuild_aggregate":["received","extracted","verifying","published"],
"reconcile":["inventory","removing_index","verifying","done"]}

class Jobs:
    def __init__(self,p):self.p=p
    def _lease(self,j):
        return JobLease(job=j["public"],work=j["work"],lease_token=j["lease_token"],expires_at=j["expires_at"])
    def _check(self,s,lease):
        j=s["jobs"].get(lease.job.id)
        require(j and j["public"]["state"]=="running" and j["lease_token"]==lease.lease_token and j["expires_at"] and datetime.fromisoformat(j["expires_at"])>now(),"lease_lost")
        require(j["lifecycle_revision"]==s["lifecycle_revision"],"capability_denied")
        return j
    def _reschedule_stale(self,s):
        """Fence old attempts, then preserve accepted independent document work."""
        for j in list(s["jobs"].values()):
            p=j["public"]
            if j["lifecycle_revision"]==s["lifecycle_revision"] or p["state"]=="completed":
                continue
            if p["state"]=="failed" and p["error_code"]!="superseded":
                continue
            p.update(state="failed",error_code="superseded",retryable=False,updated_at=iso())
            j["lease_token"]=None;j["expires_at"]=None
            docs=[s["documents"].get(did) for did in j["work"]["document_ids"]]
            # A later command owns that document's state. Erasure may have removed
            # restricted input; such work cannot be silently reconstructed.
            owned=bool(docs) and all(d and d["latest_job_id"]==p["id"] for d in docs)
            if owned:
                for d in docs:d["processing_state"]="failed"
            if s["write_barrier"] or j.get("rescheduled_to") or j.get("resumption_forbidden") or not owned:
                continue
            if p["kind"] not in ("ingest","activate","deactivate") or any(d.get("deleted") or d["ai_status"]!=("inactive" if p["kind"]=="deactivate" else "active") for d in docs):
                continue
            if p["kind"]=="ingest" and p["stage"] in ("received","parsed") and any("raw" not in d for d in docs):
                continue
            refs=j["work"]["record_versions"]
            if any(ref["record_id"] not in s["records"] or s["records"][ref["record_id"]]["record_version"]!=ref["record_version"] for ref in refs):
                continue
            operations=[op for op in s["operations"].values() if op["public"]["job_id"]==p["id"]]
            # No new writer can race an unresolved old network call. Late reports
            # still use the old completion ticket, while old SQL tokens stay dead.
            if any(op["public"]["state"] in ("in_flight","unknown") for op in operations):
                continue
            for op in operations:
                if op["public"]["state"]=="pending":
                    op["public"]["state"]="failed"
                    op["outcome"]=dict(state="failed",completed_entry_ids=[],error_code="superseded",observed_at=iso())
            removal=sorted(set(j["work"]["removal_entry_ids"]) | {eid for op in operations if op["public"]["action"]=="upsert" for eid in op["public"]["entry_ids"]})
            replacement=self.p._new_job(s,p["project_id"],p["kind"],docs=j["work"]["document_ids"],refs=refs,removals=removal)
            fresh=s["jobs"][replacement.id]
            if p["kind"]=="ingest":
                fresh["public"]["stage"]=p["stage"] if p["stage"] in ("received","parsed") else "privacy_ready"
            # Old checkpoints remain ineligible; the new job has its own checkpoint
            # keys and publication generation, after removing obsolete external IDs.
            j["rescheduled_to"]=replacement.id
            for d in docs:d.update(latest_job_id=replacement.id,processing_state="pending",updated_at=iso())

    async def claim(self,worker_id,kinds):
        async with self.p.db.connection(restricted=True) as c:
            rows=await (await c.execute("SELECT ps.project_id AS id FROM project_state ps JOIN projects p ON p.id=ps.project_id ORDER BY p.created_at,p.id FOR UPDATE OF ps SKIP LOCKED")).fetchall()
            for row in rows:
                s=await self.p.load_relational_project(c,row["id"],restricted=True)
                self._reschedule_stale(s)
                for j in s["jobs"].values():
                    p=j["public"]
                    if p["kind"] not in kinds:continue
                    if p["state"] not in ("pending","running"):continue
                    if j["lifecycle_revision"]!=s["lifecycle_revision"]:
                        p.update(state="failed",error_code="superseded",retryable=False,updated_at=iso());continue
                    if s["write_barrier"] and p["kind"] not in ("erase_person","delete_document","reconcile"):continue
                    if p["state"]=="running" and j["expires_at"] and datetime.fromisoformat(j["expires_at"])>now():continue
                    p.update(state="running",updated_at=iso());j["lease_token"]=secrets.token_urlsafe(32);j["expires_at"]=(now()+timedelta(seconds=self.p.lease_seconds)).isoformat();j["worker_id"]=worker_id
                    await self.p.sync_relational(c,row["id"],s,restricted=True)
                    return self._lease(j)
                await self.p.sync_relational(c,row["id"],s,restricted=True)
        return None
    async def _mutate(self,lease,fn):
        async with self.p.db.connection(restricted=True) as c:
            s=await self.p.load_relational_project(c,lease.job.project_id,restricted=True,for_update=True);require(s,"lease_lost")
            j=self._check(s,lease);result=fn(s,j)
            await self.p.sync_relational(c,lease.job.project_id,s,restricted=True)
            return result
    async def heartbeat(self,lease):
        def apply(s,j):
            j["expires_at"]=(now()+timedelta(seconds=self.p.lease_seconds)).isoformat()
            return self._lease(j)
        return await self._mutate(lease,apply)
    async def advance(self,lease,expected_stage,next_stage,counts):
        def apply(s,j):
            seq=SEQUENCES[j["public"]["kind"]]
            require(j["public"]["stage"]==expected_stage and next_stage in seq and seq.index(next_stage)==seq.index(expected_stage)+1,"contract_violation")
            require(next_stage not in ("published","done"),"contract_violation")
            j["public"].update(stage=next_stage,counts=counts,updated_at=iso())
            return self._lease(j)
        return await self._mutate(lease,apply)
    async def capability(self,lease,stage):
        def apply(s,j):
            require(stage==j["public"]["stage"],"capability_denied")
            cap=JobCapability(capability_id=uid(),job_id=j["public"]["id"],project_id=j["public"]["project_id"],lease_token=j["lease_token"],lifecycle_revision=j["lifecycle_revision"],allowed_stage=stage,allowed_record_versions=j["work"]["record_versions"],publication_generation=j["publication_generation"],expires_at=j["expires_at"])
            s["capabilities"][cap.capability_id]=dump(cap);return cap
        return await self._mutate(lease,apply)
    async def fail(self,lease,code,retryable):
        def apply(s,j):
            j["public"].update(state="failed",error_code=code,retryable=retryable,updated_at=iso())
            self.p._recoverable_cleanup(j)
            for did in j["work"]["document_ids"]:
                if did in s["documents"]:s["documents"][did]["processing_state"]="failed"
            return Job.model_validate(j["public"])
        return await self._mutate(lease,apply)
    async def save_results(self,lease,results):
        def apply(s,j):
            j["results"]=[dump(x) for x in results];return self._lease(j)
        return await self._mutate(lease,apply)

    def _apply_batches(self,s,j,results):
        expected={ref["record_id"] for ref in j["work"]["record_versions"]} if j["public"]["kind"] != "rebuild_aggregate" else set()
        produced=set()
        for result in results:
            if not result.batch_id:continue
            saved=next((v for v in s["checkpoints"].values() if v["batch"]["batch_id"]==result.batch_id and v["batch"]["job_id"]==j["public"]["id"]),None);require(saved)
            require(saved["lifecycle_revision"]==s["lifecycle_revision"])
            batch=ArtifactBatch.model_validate(saved["batch"])
            for dep in batch.dependencies:self.p._dependency(s,dep,staged=True)
            for e in batch.index_entries:
                successful=any(op["public"]["action"]=="upsert" and e.id in op["public"]["entry_ids"] and op["public"]["state"]=="succeeded" for op in s["operations"].values() if op["public"]["job_id"]==j["public"]["id"])
                require(successful,"index_outcome_unknown")
                s["entries"][e.id]=dump(e)
            for memory in batch.memories:s["memories"][memory.id]=dict(data=dump(memory),valid=True)
            for ch in batch.chunks:s["chunks"][ch.id]=dump(ch)
            for event in batch.proposed_history:s["history"][event.id]=dump(event)
            record_ids={ch.record_id for ch in batch.chunks}
            for rid in record_ids:
                r=s["records"][rid];r["chunk_ids"]=[ch.id for ch in sorted(batch.chunks,key=lambda x:x.ordinal) if ch.record_id==rid]
                r["entry_ids"]=[e.id for e in batch.index_entries if e.record_id==rid];r["published"]=True;r["quarantined"]=False;produced.add(rid)
        require(expected<=produced or not expected)
    async def publish(self,lease,results):
        def apply(s,j):
            seq=SEQUENCES[j["public"]["kind"]];kind=j["public"]["kind"]
            require(j["public"]["stage"]==seq[-2])
            for result in results:
                for opid in result.operation_ids:
                    op=s["operations"].get(opid);require(op and op["public"]["state"]=="succeeded","index_outcome_unknown")
            if kind in ("erase_person","delete_document","reconcile"):
                outstanding=[op for op in s["operations"].values() if op["public"]["state"] in ("pending","in_flight","unknown") and op["public"]["lifecycle_revision"]<=j["lifecycle_revision"]]
                require(not outstanding,"index_outcome_unknown")
                for eid in j["work"]["removal_entry_ids"]:
                    require(any(op["public"]["action"]=="delete" and eid in op["public"]["entry_ids"] and op["public"]["state"]=="succeeded" for op in s["operations"].values() if op["public"]["job_id"]==j["public"]["id"]),"index_outcome_unknown")
            if kind in ("ingest","activate","erase_person","rebuild_aggregate"):self._apply_batches(s,j,results)
            if kind=="rebuild_aggregate" and j.get("staged_overview"):
                self.p._validate_candidate(s,j["public"]["project_id"],ReviewedCandidate.model_validate(j["staged_overview"]["candidate"]))
                s["overview"]=j.pop("staged_overview")
            if kind in ("ingest","activate","erase_person","deactivate"):
                for did in j["work"]["document_ids"]:
                    if did in s["documents"] and not s["documents"][did].get("deleted"):s["documents"][did].update(processing_state="completed",updated_at=iso())
                self.p._invalidate(s)
                # Aggregate jobs follow publication; no circular dependency on base visibility.
                affected_docs=set(j["work"]["document_ids"])
                affected_records={x["record_id"] for x in j["work"]["record_versions"]}
                refs=[RecordVersionRef(record_id=r["record_id"],record_version=r["record_version"]) for r in s["records"].values() if (r["record_id"] in affected_records or r["original_doc_id"] in affected_docs) and r["published"] and not r.get("quarantined") and not s["documents"][r["original_doc_id"]].get("deleted") and s["documents"][r["original_doc_id"]]["ai_status"]=="active"]
                if refs:
                    plan=RebuildPlan(id=uid(),project_id=j["public"]["project_id"],record_versions=refs,memory_ids=[mid for mid,m in s["memories"].items() if m["valid"]],obsolete_entry_ids=[],dependencies=[Dependency(record_id=x.record_id,record_version=x.record_version,span_ids=[sp["span_id"] for sp in s["records"][x.record_id]["spans"]]) for x in refs],snapshot=self.p.snapshot(s))
                    s["plans"][plan.id]=dump(plan);self.p._new_job(s,j["public"]["project_id"],"rebuild_aggregate",refs=refs,plans=[plan.id])
            if kind in ("erase_person","delete_document"):
                # Content-bearing old checkpoints and obsolete index payloads were inventoried.
                for eid in j["work"]["removal_entry_ids"]:s["entries"].pop(eid,None)
                for operation in s["operations"].values():
                    if set(operation["public"]["entry_ids"]) & set(j["work"]["removal_entry_ids"]):
                        operation["input"]["entries"] = []
                for pid in j["work"]["person_ids"]:
                    require(not any(person_occurs(r,pid,s["people"]) for r in s["records"].values()),"contract_violation")
                    s["people"].pop(pid,None)
                s["write_barrier"]=False
            j["public"].update(state="completed",stage=seq[-1],error_code=None,retryable=False,updated_at=iso())
            j["lease_token"]=None;j["expires_at"]=None
            # Capabilities are ephemeral authorization, never retain expired credentials.
            s["capabilities"]={key:cap for key,cap in s["capabilities"].items() if cap["job_id"]!=j["public"]["id"]}
            return Job.model_validate(j["public"])
        # Publication retry after a lost response is idempotent.
        async with self.p.db.connection(restricted=True) as c:
            state=await self.p.load_relational_project(c,lease.job.project_id,restricted=True)
            if state and state["jobs"].get(lease.job.id,{}).get("public",{}).get("state")=="completed":
                return Job.model_validate(state["jobs"][lease.job.id]["public"])
        return await self._mutate(lease,apply)

    async def prepare_ingestion(self,lease):
        if lease.job.stage == "parsed":
            def read_private(s,j):
                rows=[]
                for ref in j["work"]["record_versions"]:
                    record=s["records"][ref["record_id"]]
                    title_span={"span_id":"title:"+record["record_id"],"text":s["documents"][record["original_doc_id"]]["raw_filename"]}
                    saved=s.get("privacy_plans",{}).get(f"{record['record_id']}:{record['record_version']}")
                    resolutions=[value for value in s.get("privacy_resolutions",{}).values()
                                 if value["record_id"]==record["record_id"] and
                                 value["record_version"]==record["record_version"] and
                                 value.get("source_hash")==record["source_hash"]]
                    rows.append((record,[title_span,*record["raw_spans"]],saved,dict(s["people"]),resolutions,s["privacy_generation"]))
                return rows
            private_records=await self._mutate(lease,read_private)
            agent=getattr(self.p,"privacy_agent",None)
            if agent is None:raise DomainError("provider_unavailable")
            plans=[]
            model=getattr(getattr(agent.provider,"settings",None),"model",None) or "configured-model"
            for record,spans,saved,people,resolutions,privacy_generation in private_records:
                lease=await self.heartbeat(lease)
                reusable=(saved and saved.get("complete") and saved.get("source_hash")==record["source_hash"] and
                          saved.get("policy_version")==agent.policy_version and saved.get("prompt_version")==agent.prompt_version and
                          saved.get("model_version")==model and saved.get("identity_revision")==privacy_generation and
                          all(not entity.get("identity_hint") or not entity["identity_hint"].startswith("PERSON_") or
                              entity["identity_hint"] in people for entity in saved.get("entities",[])))
                if reusable:plans.append(PrivacyPlan.model_validate(saved))
                else:plans.append(await agent.plan(lease.job.project_id,record["record_id"],record["record_version"],spans,
                    record["source_hash"],people,resolutions,privacy_generation))
                lease=await self.heartbeat(lease)

            def persist(s,j):
                new_ids={}
                for incoming in plans:
                    plan=dump(incoming);record=s["records"][plan["record_id"]]
                    require(record["record_version"]==plan["record_version"] and record["source_hash"]==plan["source_hash"],"evidence_changed")
                    by_id={"title:"+record["record_id"]:s["documents"][record["original_doc_id"]]["raw_filename"],
                           **{span["span_id"]:span["text"] for span in record["raw_spans"]}}
                    unresolved=set(plan["unresolved_reasons"])
                    aliases={}
                    for pid,person in s["people"].items():
                        for alias in [person["display_name"],*[contact["value"] for contact in person.get("contacts",[])]]:
                            aliases.setdefault(alias.casefold(),set()).add(pid)
                    approved_bindings=set()
                    for resolution in s.get("privacy_resolutions",{}).values():
                        if resolution["decision"].startswith("bind:"):
                            approved_bindings.add((resolution["span_id"],resolution["start"],resolution["end"],resolution["decision"][5:]))
                    for entity in plan["entities"]:
                        if entity["kind"]=="person":
                            value=entity["expected_text"].strip();hint=entity.get("identity_hint")
                            if entity["confidence"]=="uncertain":
                                unresolved.add("uncertain person identity")
                            elif hint in s["people"]:
                                matches=aliases.get(value.casefold(),set())
                                approved=(entity["span_id"],entity["start"],entity["end"],hint) in approved_bindings
                                if hint not in matches or len(matches)>1 and not approved:unresolved.add("unsupported identity binding")
                            elif hint and hint.startswith("NEW_"):
                                pid=_proposed_person_id(plan["plan_id"],hint,value,aliases,new_ids)
                                if pid is None:
                                    unresolved.add("same-name identity requires admin resolution")
                                else:
                                    if pid not in s["people"]:
                                        s["people"][pid]=dump(Person(id=pid,display_name=value,kind="client",contacts=[],state="active"))
                                    entity["identity_hint"]=pid
                            else:unresolved.add("person lacks evidence-bound identity proposal")
                        elif entity["kind"]=="uncertain":unresolved.add("semantic classification unresolved")
                    for edit in plan["edits"]:
                        entity=next((value for value in plan["entities"] if value["span_id"]==edit["span_id"] and value["start"]<=edit["start"] and value["end"]>=edit["end"]),None)
                        if edit["reason"]=="identity":
                            if not entity or entity.get("identity_hint") not in s["people"]:unresolved.add("identity edit is unresolved");continue
                            edit["replacement"]=entity["identity_hint"]
                        elif edit["reason"] in ("contact","personal_identifier"):
                            edit["replacement"]=entity.get("identity_hint") if entity and entity.get("identity_hint") in s["people"] else "[contact removed]"
                        elif edit["reason"]=="private_cause":edit["replacement"]="[private cause removed]"
                    for span_id,edits in __import__("itertools").groupby(sorted(plan["edits"],key=lambda value:(value["span_id"],value["start"])),lambda value:value["span_id"]):
                        shift=0
                        for edit in edits:
                            edit["sanitized_start"]=edit["start"]+shift
                            edit["sanitized_end"]=edit["sanitized_start"]+len(edit["replacement"])
                            shift+=len(edit["replacement"])-(edit["end"]-edit["start"])
                    plan["unresolved_reasons"]=sorted(unresolved)
                    s.setdefault("privacy_plans",{})[f"{plan['record_id']}:{plan['record_version']}"]=plan
                    for diagnostic_id,value in list(s.setdefault("privacy_diagnostics",{}).items()):
                        if value["record_id"]==plan["record_id"] and value["record_version"]==plan["record_version"] and value["state"]=="open":
                            s["privacy_diagnostics"].pop(diagnostic_id)
                    actionable=[entity for entity in plan["entities"] if entity["confidence"]=="uncertain" or
                                entity["kind"]=="uncertain" or plan["unresolved_reasons"] and
                                entity["kind"] in ("person","contact","personal_identifier","contextual_circumstance")]
                    seen=set()
                    for entity in actionable:
                        key=(entity["span_id"],entity["start"],entity["end"],entity["kind"])
                        if key in seen:continue
                        seen.add(key)
                        reason="; ".join(plan["unresolved_reasons"])[:500] or "uncertain entity"
                        diagnostic=PrivacyDiagnostic(id=uid(),record_id=plan["record_id"],record_version=plan["record_version"],
                            span_id=entity["span_id"],start=entity["start"],end=entity["end"],kind=entity["kind"],reason=reason,state="open",updated_at=now())
                        s["privacy_diagnostics"][diagnostic.id]=dump(diagnostic)
                return self._lease(j)
            lease=await self._mutate(lease,persist)
        def apply(s,j):
            stage=j["public"]["stage"]
            if stage=="received":
                refs=[]
                for did in j["work"]["document_ids"]:
                    d=s["documents"][did];parsed=parse(d["raw"],d["record_type"])
                    for spans,time,source_hash in parsed:
                        rid=uid();duplicate=next((r["duplicate_of"] or r["record_id"] for r in s["records"].values() if r.get("source_hash")==source_hash),None)
                        r=dict(project_id=j["public"]["project_id"],original_doc_id=did,record_id=rid,record_version=1,record_type=d["record_type"],title=d["title"],source_time=dump(time),spans=[dump(sp) for sp in spans],person_ids=[],duplicate_of=duplicate,published=False,quarantined=True,chunk_ids=[],entry_ids=[],source_hash=source_hash,created_at=iso(),raw_spans=[dump(sp) for sp in spans])
                        s["records"][rid]=r;refs.append(dump(RecordVersionRef(record_id=rid,record_version=1)))
                    d["processing_state"]="running"
                j["work"]["record_versions"]=refs;j["public"].update(stage="parsed",updated_at=iso())
                return self._lease(j)
            if j["public"]["stage"]=="parsed":
                for ref in j["work"]["record_versions"]:
                    r=s["records"][ref["record_id"]];plan=s.get("privacy_plans",{}).get(f"{r['record_id']}:{r['record_version']}")
                    require(plan and plan["complete"] and plan["source_hash"]==r["source_hash"],"privacy_unresolved")
                    edits={}
                    for edit in plan["edits"]:edits.setdefault(edit["span_id"],[]).append(edit)
                    ids={entity["identity_hint"] for entity in plan["entities"] if entity.get("identity_hint") in s["people"]}
                    for sp in r["raw_spans"]:
                        text=sp["text"]
                        for edit in reversed(sorted(edits.get(sp["span_id"],[]),key=lambda value:value["start"])):
                            require(text[edit["start"]:edit["end"]]==edit["expected_text"],"privacy_unresolved")
                            text=text[:edit["start"]]+edit["replacement"]+text[edit["end"]:]
                        r["spans"][sp["ordinal"]]["text"]=text
                    title_id="title:"+r["record_id"];title=s["documents"][r["original_doc_id"]]["raw_filename"]
                    for edit in reversed(sorted(edits.get(title_id,[]),key=lambda value:value["start"])):
                        require(title[edit["start"]:edit["end"]]==edit["expected_text"],"privacy_unresolved")
                        title=title[:edit["start"]]+edit["replacement"]+title[edit["end"]:]
                    sanitized={span["span_id"]:r["spans"][span["ordinal"]]["text"] for span in r["raw_spans"]}
                    sanitized[title_id]=title
                    resolutions=[value for value in s.get("privacy_resolutions",{}).values()
                                 if value["record_id"]==r["record_id"] and
                                 value["record_version"]==r["record_version"] and
                                 value.get("source_hash")==r["source_hash"]]
                    try:validate_sanitized(plan,sanitized,resolutions)
                    except ValueError:raise DomainError("privacy_unresolved") from None
                    r["title"]=title;r["person_ids"]=sorted(ids);r["quarantined"]=bool(plan["unresolved_reasons"])
                    s["documents"][r["original_doc_id"]]["title"]=r["title"]
                if any(s["records"][ref["record_id"]]["quarantined"] for ref in j["work"]["record_versions"]):
                    j["public"].update(state="failed",error_code="privacy_unresolved",retryable=True,updated_at=iso())
                    for did in j["work"]["document_ids"]:s["documents"][did]["processing_state"]="failed"
                    return self._lease(j)
                j["public"].update(stage="privacy_ready",updated_at=iso())
            return self._lease(j)
        return await self._mutate(lease,apply)

    async def prepare_cleanup(self,lease):
        def apply(s,j):
            kind=j["public"]["kind"]
            if j["public"]["stage"]=="invalidating":
                j["public"]["stage"]="inventory"
                return self._lease(j)
            if j["public"]["stage"]=="inventory":
                # Inventory all pending/late entries; project-wide barrier prevents new writers.
                oldentries={eid for op in s["operations"].values() if op["public"]["lifecycle_revision"]<j["lifecycle_revision"] and (op["public"]["state"] in ("pending","in_flight","unknown") or any(e["original_doc_id"] in j["work"]["document_ids"] or set(e["person_ids"]) & set(j["work"]["person_ids"]) for e in op["input"]["entries"])) for eid in op["public"]["entry_ids"] if op["public"]["action"]=="upsert"}
                j["work"]["removal_entry_ids"]=sorted(set(j["work"]["removal_entry_ids"])|oldentries)
                j["public"]["stage"]="draining"
                return self._lease(j)
            if j["public"]["stage"]=="draining":
                outstanding=[op for op in s["operations"].values() if op["public"]["lifecycle_revision"]<j["lifecycle_revision"] and op["public"]["state"] in ("in_flight","unknown")]
                # Prepared but never dispatched operations are safely canceled under barrier.
                for op in s["operations"].values():
                    if op["public"]["lifecycle_revision"]<j["lifecycle_revision"] and op["public"]["state"]=="pending":
                        op["public"]["state"]="failed";op["outcome"]=dict(state="failed",completed_entry_ids=[],error_code="superseded",observed_at=iso())
                require(not outstanding,"index_outcome_unknown")
                j["public"]["stage"]="sanitizing"
                return self._lease(j)
            if j["public"]["stage"]=="sanitizing":
                affected=set(j["work"]["document_ids"]);person_ids=j["work"]["person_ids"]
                if kind=="delete_document":
                    record_ids={rid for rid,r in s["records"].items() if r["original_doc_id"] in affected}
                    for did in affected:s["documents"].pop(did,None)
                    for rid in record_ids:s["records"].pop(rid,None)
                else:
                    record_ids=set()
                    for pid in person_ids:
                        for rid,r in s["records"].items():
                            if not person_occurs(r,pid,s["people"]):continue
                            normalized=[normalize(sp["text"],s["people"]) for sp in r["spans"]]
                            title=normalize(r["title"],s["people"])
                            require(not title.ambiguous and not any(value.ambiguous for value in normalized),"ambiguous_person")
                            record_ids.add(rid)
                            r["record_version"]+=1;r["published"]=False;r["quarantined"]=False
                            r["title"]=title.text.replace(pid,"[deleted user]")
                            for sp,value in zip(r["spans"],normalized):sp["text"]=value.text.replace(pid,"[deleted user]")
                            r["person_ids"]=[x for x in r["person_ids"] if x!=pid]
                            r.pop("raw_spans",None);r.pop("source_hash",None)
                            r["chunk_ids"]=[];r["entry_ids"]=[]
                    # Retained raw uploads are deleted project-wide; safe normalized facts remain.
                    # This avoids global replacement of a shared, ambiguous name.
                    for d in s["documents"].values():d.pop("raw",None);d.pop("raw_filename",None)
                    for r in s["records"].values():r.pop("raw_spans",None)
                    # Pending uploads cannot be proven sanitized; fail visibly with no content retained.
                    for job in s["jobs"].values():
                        if job is not j and job["public"]["state"]!="completed" and job["public"]["kind"]=="ingest":
                            job["public"].update(state="failed",error_code="superseded",retryable=False)
                            job["resumption_forbidden"]=True
                            for did in job["work"]["document_ids"]:
                                if did in s["documents"]:s["documents"][did]["processing_state"]="failed"
                    for pid in person_ids:
                        person=s["people"][pid]
                        for msg in s["messages"].values():
                            if msg.get("text"):
                                result=normalize(msg["text"],s["people"])
                                msg["text"]=result.text.replace(pid,"[deleted user]")
                        for d in s["documents"].values():d["title"]=normalize(d["title"],s["people"]).text.replace(pid,"[deleted user]")
                    j["work"]["record_versions"]=[dump(RecordVersionRef(record_id=rid,record_version=s["records"][rid]["record_version"])) for rid in sorted(record_ids)]
                # All answers are current-state cached material, invalidated above and erased now.
                s["answers"]={};s["attempts"]={}
                for msg in s["messages"].values():
                    if msg["role"]=="assistant":msg.update(state="unavailable",answer_id=None,text=None,unavailable_reason="evidence_changed")
                for mid,m in list(s["memories"].items()):
                    if any(d["record_id"] in record_ids for d in m["data"]["dependencies"]):s["memories"].pop(mid,None)
                for hid,h in list(s["history"].items()):
                    if any(r["record_id"] in record_ids for r in h["evidence"]):s["history"].pop(hid,None)
                for cid,ch in list(s["chunks"].items()):
                    if ch["record_id"] in record_ids:s["chunks"].pop(cid,None)
                s["checkpoints"]={key:v for key,v in s["checkpoints"].items() if v["batch"]["job_id"]==j["public"]["id"] or not any(d["record_id"] in record_ids for d in v["batch"]["dependencies"])}
                s["plans"]={};s["overview"]=None
                for key,plan in list(s.get("privacy_plans",{}).items()):
                    if plan["record_id"] in record_ids:s["privacy_plans"].pop(key)
                for key,diagnostic in list(s.get("privacy_diagnostics",{}).items()):
                    if diagnostic["record_id"] in record_ids:s["privacy_diagnostics"].pop(key)
                for key,resolution in list(s.get("privacy_resolutions",{}).items()):
                    if resolution["record_id"] in record_ids:s["privacy_resolutions"].pop(key)
                for oldjob in s["jobs"].values():oldjob.pop("staged_overview",None)
                j["public"]["stage"]="rebuilding"
            return self._lease(j)
        return await self._mutate(lease,apply)

class Ledger:
    def __init__(self,p):self.p=p
    async def prepare(self,cap,input):
        async with self.p.cap_transaction(cap) as (_,s):
            j=s["jobs"][cap.job_id];require(input.entry_ids and len(set(input.entry_ids))==len(input.entry_ids))
            if input.action=="upsert":
                require([e.id for e in input.entries]==input.entry_ids)
                staged={e["id"]:e for v in s["checkpoints"].values() if v["batch"]["job_id"]==cap.job_id for e in v["batch"]["index_entries"]}
                require(all(staged.get(e.id)==dump(e) for e in input.entries))
            else:require(not input.entries and set(input.entry_ids)<=set(j["work"]["removal_entry_ids"]),"capability_denied")
            for op in s["operations"].values():
                if op["public"]["job_id"]==cap.job_id and op["key"]==input.idempotency_key:
                    require(op["input"]==dump(input))
                    return OperationTicket(operation=op["public"],completion_token=op["completion_token"])
            operation=IndexOperation(id=uid(),job_id=cap.job_id,project_id=cap.project_id,action=input.action,entry_ids=input.entry_ids,lifecycle_revision=cap.lifecycle_revision,state="pending")
            token=secrets.token_urlsafe(32)
            s["operations"][operation.id]=dict(public=dump(operation),input=dump(input),key=input.idempotency_key,completion_token=token,outcome=None)
            return OperationTicket(operation=operation,completion_token=token)
    async def start(self,cap,operation_id):
        async with self.p.cap_transaction(cap) as (_,s):
            op=s["operations"].get(operation_id);require(op and op["public"]["job_id"]==cap.job_id,"capability_denied")
            # Succeeded idempotent delete can be verified again without resetting its outcome.
            if op["public"]["state"]=="succeeded":return
            require(op["public"]["state"] in ("pending","failed") or op["public"]["action"]=="delete" and op["public"]["state"] in ("unknown","in_flight"),"index_outcome_unknown")
            op["public"]["state"]="in_flight";op["outcome"]=None
    async def report(self,ticket,outcome):
        async with self.p.db.connection(restricted=True) as c:
            s=await self.p.load_relational_project(c,ticket.operation.project_id,restricted=True,for_update=True);require(s,"capability_denied")
            op=s["operations"].get(ticket.operation.id)
            require(op and secrets.compare_digest(op["completion_token"],ticket.completion_token),"capability_denied")
            require(set(outcome.completed_entry_ids)<=set(op["public"]["entry_ids"]))
            if outcome.state=="succeeded":require(set(outcome.completed_entry_ids)==set(op["public"]["entry_ids"]))
            if op["public"]["state"]=="succeeded":
                require(outcome.state=="succeeded" and set(outcome.completed_entry_ids)==set(op["outcome"]["completed_entry_ids"]))
            elif op["public"]["state"]=="failed":
                require(outcome.state=="failed" or outcome.state=="succeeded","index_outcome_unknown")
            op["outcome"]=dump(outcome);op["public"]["state"]=outcome.state
            await self.p.sync_relational(c,ticket.operation.project_id,s,restricted=True)
    async def list_operations(self,cap,page):
        async with self.p.cap_transaction(cap) as (_,s):
            items=[IndexOperation.model_validate(x["public"]) for x in s["operations"].values()]
            return self.p._page(items,page,["operations",cap.project_id,cap.job_id,cap.lifecycle_revision])
    async def get_entries(self,cap,entry_ids):
        async with self.p.cap_transaction(cap) as (_,s):
            result=[]
            for eid in entry_ids:
                e=s["entries"].get(eid)
                if e:
                    ref=CandidateRef(entry_id=e["id"],record_id=e["record_id"],record_version=e["record_version"],chunk_id=e["chunk_id"],input_hash=e["input_hash"],rank=1)
                    if self.p._candidate(s,ref,SearchFilters()):result.append(IndexEntry.model_validate(e))
            return result

async def run_once(platform,handlers,worker_id="worker"):
    """Claim and execute one job; durable checkpoints make each restart idempotent."""
    jobs=platform.jobs
    lease=await jobs.claim(worker_id,list(SEQUENCES))
    if lease is None:return False
    async def heartbeat():
        while True:
            await asyncio.sleep(max(1,platform.lease_seconds//3))
            await jobs.heartbeat(lease)
    beat=asyncio.create_task(heartbeat())
    try:
        kind=lease.job.kind;results=[]
        if kind in ("ingest","activate") and lease.work.removal_entry_ids:
            removed=await jobs._mutate(lease,lambda s,j:j.get("obsolete_index_removed",False))
            if not removed:
                cap=await jobs.capability(lease,lease.job.stage)
                await handlers.remove_index_entries(cap,lease.work.removal_entry_ids)
                # Commit before any replacement upsert. A later restart must not
                # delete a replacement that reused an immutable point ID.
                await jobs._mutate(lease,lambda s,j:j.update(obsolete_index_removed=True))
        if kind=="ingest":
            while lease.job.stage in ("received","parsed"):
                lease=await jobs.prepare_ingestion(lease)
                if lease.job.state=="failed":return True
            if lease.job.stage=="privacy_ready":
                cap=await jobs.capability(lease,lease.job.stage)
                for ref in lease.work.record_versions:results.append(await handlers.process_record(cap,ref))
                lease=await jobs.save_results(lease,results)
                lease=await jobs.advance(lease,"privacy_ready","extracted",{"records":len(lease.work.record_versions)})
            if lease.job.stage=="extracted":lease=await jobs.advance(lease,"extracted","indexed",lease.job.counts)
        elif kind=="activate":
            if lease.job.stage=="received":lease=await jobs.advance(lease,"received","rebuilding",{})
            if lease.job.stage=="rebuilding":
                cap=await jobs.capability(lease,"rebuilding")
                for ref in lease.work.record_versions:results.append(await handlers.process_record(cap,ref))
                lease=await jobs.save_results(lease,results)
                lease=await jobs.advance(lease,"rebuilding","indexed",{"records":len(lease.work.record_versions)})
        elif kind in ("erase_person","delete_document"):
            while lease.job.stage in ("invalidating","inventory","draining","sanitizing"):lease=await jobs.prepare_cleanup(lease)
            if lease.job.stage=="rebuilding":
                cap=await jobs.capability(lease,"rebuilding")
                for ref in lease.work.record_versions:results.append(await handlers.process_record(cap,ref))
                lease=await jobs.save_results(lease,results)
                lease=await jobs.advance(lease,"rebuilding","removing_index",{"records":len(lease.work.record_versions)})
            if lease.job.stage=="removing_index":
                cap=await jobs.capability(lease,"removing_index")
                removal=await handlers.remove_index_entries(cap,lease.work.removal_entry_ids) if lease.work.removal_entry_ids else None
                async with platform.cap_transaction(cap) as (_,s):results=[MaintenanceResult.model_validate(x) for x in s["jobs"][lease.job.id]["results"]]
                if removal:results.append(removal)
                lease=await jobs.save_results(lease,results)
                lease=await jobs.advance(lease,"removing_index","verifying",lease.job.counts)
        elif kind=="deactivate":
            if lease.job.stage=="invalidating":lease=await jobs.advance(lease,"invalidating","rebuilding",{})
            if lease.job.stage=="rebuilding":
                cap=await jobs.capability(lease,"rebuilding")
                if lease.work.removal_entry_ids:results.append(await handlers.remove_index_entries(cap,lease.work.removal_entry_ids))
                lease=await jobs.save_results(lease,results)
                lease=await jobs.advance(lease,"rebuilding","verifying",{})
        elif kind=="rebuild_aggregate":
            if lease.job.stage=="received":
                cap=await jobs.capability(lease,"received")
                for plan_id in lease.work.rebuild_plan_ids:
                    plan=await platform.load_rebuild_plan(cap,plan_id);results.append(await handlers.rebuild_affected(cap,plan))
                lease=await jobs.save_results(lease,results)
                lease=await jobs.advance(lease,"received","extracted",{})
            if lease.job.stage=="extracted":lease=await jobs.advance(lease,"extracted","verifying",{})
        elif kind=="reconcile":
            cap=await jobs.capability(lease,lease.job.stage);report=await handlers.reconcile(cap)
            require(not report.unresolved_operation_ids and not report.missing_entry_ids and not report.obsolete_entry_ids,"index_outcome_unknown")
            if lease.job.stage=="inventory":lease=await jobs.advance(lease,"inventory","removing_index",{})
            if lease.job.stage=="removing_index":lease=await jobs.advance(lease,"removing_index","verifying",{})
        cap=await jobs.capability(lease,lease.job.stage)
        async with platform.cap_transaction(cap) as (_,s):results=[MaintenanceResult.model_validate(x) for x in s["jobs"][lease.job.id]["results"]]
        await jobs.publish(lease,results)
    except DomainError as exc:
        try:await jobs.fail(lease,exc.code,exc.retryable or exc.code in ("index_outcome_unknown","lease_lost"))
        except DomainError:pass
    except Exception:
        try:await jobs.fail(lease,"internal_error",True)
        except DomainError:pass
    finally:
        beat.cancel()
        try:await beat
        except asyncio.CancelledError:pass
    return True
