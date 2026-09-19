"""Focused actual index race and shared-name regressions for evidence repairs."""
import asyncio,json,os,secrets
from pathlib import Path
from dotenv import load_dotenv
from app.contracts.models import *
from app.contracts.errors import DomainError
from app.evidence.jobs import run_once
from live_helpers import build

async def main():
    p,b,provider,index=build("a_repair_race2_0919",secrets.token_hex(32))
    out=Path("artifacts/evidence/repair_review_0919/regressions-final.json")
    observations=[]
    def note(case,**data):
        observations.append(dict(case=case,**data));out.write_text(json.dumps(observations,indent=2));print(json.dumps(observations[-1]),flush=True)
    await p.db.migrate()
    password=secrets.token_urlsafe(24);user=await p.bootstrap_user("repair@synthetic.invalid",password,"Synthetic admin")
    project=await p.bootstrap_project("Focused repair",user)
    login=await p.login("repair@synthetic.invalid",password);principal=await p.authenticate(login.session_token)
    async def ctx():return await p.authorize(principal,project)
    async def state():
        async with p.db.connection() as c:return (await (await c.execute("SELECT data FROM projects WHERE id=%s",(project,))).fetchone())["data"]
    async def drain(job):
        for _ in range(30):
            result=await p.get_job(await ctx(),job.id)
            if result.state in ("completed","failed"):return result
            await run_once(p,b,"repair-regression")
        raise AssertionError("did not settle")
    async def upload(name,text):
        job=await p.submit_upload(await ctx(),UploadInput(filename=name,record_type="report",content=text.encode()))
        result=await drain(job);assert result.state=="completed",result
        s=await state();return job,s["jobs"][job.id]["work"]["document_ids"][0]
    try:
        first,did=await upload("first.txt","Date: 2026-09-01\nThe first pilot is agreed for October.")
        # Leave another accepted upload with a real committed checkpoint and paused
        # actual upsert; deactivate only the independent first source.
        pending=await p.submit_upload(await ctx(),UploadInput(filename="second.txt",record_type="report",content=b"Date: 2026-09-01\nThe second pilot is agreed for November."))
        dispatched=asyncio.Event();release=asyncio.Event();original=index.upsert
        async def paused(entries,vectors):
            dispatched.set();await release.wait();return await original(entries,vectors)
        index.upsert=paused
        async def run_to_pause():
            while not dispatched.is_set():await run_once(p,b,"repair-paused")
        writer=asyncio.create_task(run_to_pause())
        await asyncio.wait_for(dispatched.wait(),120)
        before=await state();old=before["jobs"][pending.id];old_cap=next(JobCapability.model_validate(v) for v in before["capabilities"].values() if v["job_id"]==pending.id)
        old_entry_ids=[eid for op in before["operations"].values() if op["public"]["job_id"]==pending.id for eid in op["public"]["entry_ids"]]
        deactivate=await p.mutate_document(await ctx(),did,"deactivate")
        result=await drain(deactivate);assert result.state=="completed",result
        blocked=await state();assert not blocked["jobs"][pending.id].get("rescheduled_to")
        release.set();await writer;index.upsert=original
        rejected=None
        try:await p.load_staged_record(old_cap,old_cap.allowed_record_versions[0])
        except DomainError as exc:rejected=exc.code
        assert rejected in ("lease_lost","capability_denied")
        actual_publish=p.jobs.publish
        publication_failed=False
        async def interrupted_publish(lease,results):
            nonlocal publication_failed
            if lease.job.kind=="ingest" and lease.job.id!=pending.id and not publication_failed:
                publication_failed=True
                raise DomainError("provider_unavailable")
            return await actual_publish(lease,results)
        p.jobs.publish=interrupted_publish
        for _ in range(20):
            await run_once(p,b,"repair-resume")
            after=await state();replacement=after["jobs"][pending.id].get("rescheduled_to")
            if replacement and after["jobs"][replacement]["public"]["state"] in ("failed","completed"):break
        assert replacement and publication_failed and after["jobs"][replacement]["public"]["state"]=="failed"
        assert after["jobs"][replacement]["obsolete_index_removed"]
        assert after["jobs"][replacement]["public"]["stage"]=="indexed"
        p.jobs.publish=actual_publish
        deletion_calls=[]
        actual_delete=index.delete
        async def counted_delete(ids):
            deletion_calls.append(ids)
            return await actual_delete(ids)
        index.delete=counted_delete
        retried=await p.retry_job(await ctx(),replacement)
        resumed=await drain(retried)
        assert resumed.state=="completed",resumed
        assert not deletion_calls
        index.delete=actual_delete
        after=await state()
        assert not await index.fetch(old_entry_ids)
        newdid=after["jobs"][replacement]["work"]["document_ids"][0]
        assert after["documents"][newdid]["processing_state"]=="completed"
        note("R-A2-R-A3-I-CONTRACT-inflight-independent",status="PASS",schema=p.db.schema,old_job=pending.id,replacement_job=replacement,old_capability_error=rejected,removed_entry_ids=old_entry_ids,checks=["real old upsert paused","independent mutation completes","no replacement while old network write unresolved","late upsert recorded","old capability denied","obsolete points removed before replacement","replacement coherently published","publication interrupted after real replacement index acknowledgement","retry skips already committed obsolete-point cleanup"])

        # Two same-name identities retain distinct source attribution. A separate
        # unaffected document's canonical descriptors/vectors must remain unchanged.
        first_person=await p.associate_person(await ctx(),PersonInput(display_name="Alex Reed",kind="employee",contacts=[Contact(kind="email",value="first@synthetic.invalid")]))
        second_person=await p.associate_person(await ctx(),PersonInput(display_name="Alex Reed",kind="employee",contacts=[Contact(kind="email",value="second@synthetic.invalid")]))
        same,sdid=await upload("same.txt","Date: 2026-09-01\nAlex Reed first@synthetic.invalid agreed the October pilot.\nAlex Reed second@synthetic.invalid owns the November report.")
        before=await state();unchanged={key:value for key,value in before["entries"].items() if value["original_doc_id"]==newdid}
        erase=await p.erase_person(await ctx(),first_person.id);result=await drain(erase);assert result.state=="completed",result
        after=await state();record=next(r for r in after["records"].values() if r["original_doc_id"]==sdid)
        text="\n".join(sp["text"] for sp in record["spans"])
        assert "[deleted user] agreed the October pilot." in text and second_person.id in text
        assert first_person.id not in json.dumps(after["records"])
        assert {key:value for key,value in after["entries"].items() if value["original_doc_id"]==newdid}==unchanged
        assert await index.verify([IndexEntry.model_validate(value) for value in unchanged.values()])
        note("R-A4-CT15-same-name-and-untouched",status="PASS",schema=p.db.schema,erase_job=erase.id,remaining_person=second_person.id,unchanged_entry_ids=list(unchanged),checks=["selected person attribution deleted","other same-name identity retained","both project facts retained","unrelated descriptors unchanged","unrelated real vectors verified"],events=provider.events)
    finally:
        await provider.close();await index.close();await p.db.close()
asyncio.run(main())

