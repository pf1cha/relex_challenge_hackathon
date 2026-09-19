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
from .privacy import normalize

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
    async def claim(self,worker_id,kinds):
        async with self.p.db.connection() as c:
            rows=await (await c.execute("SELECT id,data FROM projects ORDER BY created_at,id FOR UPDATE SKIP LOCKED")).fetchall()
            for row in rows:
                s=row["data"]
                for j in s["jobs"].values():
                    p=j["public"]
                    if p["kind"] not in kinds:continue
                    if p["state"] not in ("pending","running"):continue
                    if j["lifecycle_revision"]!=s["lifecycle_revision"]:
                        p.update(state="failed",error_code="superseded",retryable=False,updated_at=iso());continue
                    if s["write_barrier"] and p["kind"] not in ("erase_person","delete_document","reconcile"):continue
                    if p["state"]=="running" and j["expires_at"] and datetime.fromisoformat(j["expires_at"])>now():continue
                    p.update(state="running",updated_at=iso());j["lease_token"]=secrets.token_urlsafe(32);j["expires_at"]=(now()+timedelta(seconds=self.p.lease_seconds)).isoformat();j["worker_id"]=worker_id
                    await c.execute("UPDATE projects SET data=%s WHERE id=%s",(Jsonb(s),row["id"]))
                    return self._lease(j)
                await c.execute("UPDATE projects SET data=%s WHERE id=%s",(Jsonb(s),row["id"]))
        return None
    async def _mutate(self,lease,fn):
        async with self.p.db.connection() as c:
            row=await (await c.execute("SELECT data FROM projects WHERE id=%s FOR UPDATE",(lease.job.project_id,))).fetchone();require(row,"lease_lost")
            s=row["data"];j=self._check(s,lease);result=fn(s,j)
            await c.execute("UPDATE projects SET data=%s WHERE id=%s",(Jsonb(s),lease.job.project_id))
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
                refs=[RecordVersionRef(record_id=r["record_id"],record_version=r["record_version"]) for r in s["records"].values() if r["published"] and not r.get("quarantined") and not s["documents"][r["original_doc_id"]].get("deleted") and s["documents"][r["original_doc_id"]]["ai_status"]=="active"]
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
                    require(not any(pid in compact(r) for r in s["records"].values()),"contract_violation")
                    s["people"].pop(pid,None)
                s["write_barrier"]=False
            j["public"].update(state="completed",stage=seq[-1],error_code=None,retryable=False,updated_at=iso())
            j["lease_token"]=None;j["expires_at"]=None
            # Capabilities are ephemeral authorization, never retain expired credentials.
            s["capabilities"]={key:cap for key,cap in s["capabilities"].items() if cap["job_id"]!=j["public"]["id"]}
            return Job.model_validate(j["public"])
        # Publication retry after a lost response is idempotent.
        async with self.p.db.connection() as c:
            row=await (await c.execute("SELECT data FROM projects WHERE id=%s",(lease.job.project_id,))).fetchone()
            if row and row["data"]["jobs"].get(lease.job.id,{}).get("public",{}).get("state")=="completed":
                return Job.model_validate(row["data"]["jobs"][lease.job.id]["public"])
        return await self._mutate(lease,apply)

    async def prepare_ingestion(self,lease):
        detected = {}
        if lease.job.stage == "parsed" and self.p.privacy_detector is not None:
            def read_private(s,j):
                return [(ref["record_id"],s["records"][ref["record_id"]]["raw_spans"]) for ref in j["work"]["record_versions"]]
            private_records = await self._mutate(lease,read_private)
            for rid,spans in private_records:
                for span in spans:
                    result = await self.p.privacy_detector.detect(PrivacyDetectionInput(project_id=lease.job.project_id,record_id=rid,text=span["text"]))
                    text=span["text"];uncertain=result.unresolved;last=0;names=[]
                    changes=[]
                    for detection in sorted(result.detections,key=lambda x:x.start):
                        require(last<=detection.start<detection.end<=len(text))
                        last=detection.end
                        if detection.confidence=="uncertain":uncertain=True
                        if detection.kind in ("postal_address","private_discussion"):
                            changes.append((detection.start,detection.end,"[private context removed]"))
                        elif detection.kind=="name":names.append(text[detection.start:detection.end])
                    for start,end,replacement in reversed(changes):text=text[:start]+replacement+text[end:]
                    detected[span["span_id"]]=(text,uncertain,names)
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
                unresolved=False
                for ref in j["work"]["record_versions"]:
                    r=s["records"][ref["record_id"]];ids=set()
                    for sp in r["raw_spans"]:
                        detected_text,detected_uncertain,detected_names=detected.get(sp["span_id"],(sp["text"],False,[]))
                        known_names={person["display_name"].casefold() for person in s["people"].values()}
                        detected_uncertain |= any(name.casefold() not in known_names for name in detected_names)
                        normalized=normalize(detected_text,s["people"],ingestion=True)
                        unresolved|=detected_uncertain
                        r["spans"][sp["ordinal"]]["text"]=normalized.text;ids.update(normalized.person_ids);unresolved|=normalized.ambiguous
                    title=normalize(s["documents"][r["original_doc_id"]]["raw_filename"],s["people"],ingestion=True)
                    r["title"]=title.text;ids.update(title.person_ids);unresolved|=title.ambiguous
                    r["person_ids"]=sorted(ids);r["quarantined"]=unresolved
                    s["documents"][r["original_doc_id"]]["title"]=r["title"]
                if unresolved:
                    j["public"].update(state="failed",error_code="privacy_unresolved",retryable=True,updated_at=iso())
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
                            if pid not in r["person_ids"] and pid not in compact(r):continue
                            record_ids.add(rid)
                            r["record_version"]+=1;r["published"]=False;r["quarantined"]=False
                            r["title"]=r["title"].replace(pid,"[deleted user]")
                            for sp in r["spans"]:sp["text"]=sp["text"].replace(pid,"[deleted user]")
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
                            for did in job["work"]["document_ids"]:
                                if did in s["documents"]:s["documents"][did]["processing_state"]="failed"
                    for pid in person_ids:
                        person=s["people"][pid]
                        for msg in s["messages"].values():
                            if msg.get("text"):
                                result=normalize(msg["text"],s["people"])
                                msg["text"]=result.text.replace(pid,"[deleted user]")
                        for d in s["documents"].values():d["title"]=d["title"].replace(pid,"[deleted user]")
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
        async with self.p.db.connection() as c:
            row=await (await c.execute("SELECT data FROM projects WHERE id=%s FOR UPDATE",(ticket.operation.project_id,))).fetchone();require(row,"capability_denied")
            s=row["data"];op=s["operations"].get(ticket.operation.id)
            require(op and secrets.compare_digest(op["completion_token"],ticket.completion_token),"capability_denied")
            require(set(outcome.completed_entry_ids)<=set(op["public"]["entry_ids"]))
            if outcome.state=="succeeded":require(set(outcome.completed_entry_ids)==set(op["public"]["entry_ids"]))
            if op["public"]["state"]=="succeeded":
                require(outcome.state=="succeeded" and set(outcome.completed_entry_ids)==set(op["outcome"]["completed_entry_ids"]))
            elif op["public"]["state"]=="failed":
                require(outcome.state=="failed" or outcome.state=="succeeded","index_outcome_unknown")
            op["outcome"]=dump(outcome);op["public"]["state"]=outcome.state
            await c.execute("UPDATE projects SET data=%s WHERE id=%s",(Jsonb(s),ticket.operation.project_id))
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
