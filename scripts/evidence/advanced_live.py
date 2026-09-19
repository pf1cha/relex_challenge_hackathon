"""Real worker crash/restart, same-name erasure and in-flight release probes."""
import argparse,asyncio,json,os,secrets,sys
from pathlib import Path
from app.contracts.models import *
from app.contracts.errors import DomainError
from app.evidence.jobs import run_once
from live_helpers import build
async def main():
    parser=argparse.ArgumentParser();parser.add_argument("--run-id",required=True);args=parser.parse_args()
    schema="a_adv_"+args.run_id.replace("-","_")
    secret=secrets.token_hex(32);p,b,provider,index=build(schema,secret)
    output=Path("artifacts/evidence")/args.run_id;output.mkdir(parents=True,exist_ok=True)
    observations=[]
    def note(case,**data):
        observations.append(dict(case=case,**data));(output/"advanced.json").write_text(json.dumps(observations,indent=2));print(json.dumps(observations[-1]),flush=True)
    await p.db.migrate();password=secrets.token_urlsafe(24)
    admin=await p.bootstrap_user("admin@synthetic.invalid",password,"Admin")
    member=await p.bootstrap_user("member@synthetic.invalid",password,"Member")
    project=await p.bootstrap_project("Advanced synthetic",admin)
    async def principal(email):
        login=await p.login(email,password);return await p.authenticate(login.session_token)
    ap=await principal("admin@synthetic.invalid");mp=await principal("member@synthetic.invalid")
    async def ctx():return await p.authorize(ap,project)
    await p.set_member(await ctx(),member,"member")
    async def reject(code,call):
        try:await call
        except DomainError as e:assert e.code==code,(e.code,code);return
        raise AssertionError("expected "+code)
    async def drain(job):
        for _ in range(30):
            state=await p.get_job(await ctx(),job.id)
            if state.state in ("failed","completed"):return state
            await run_once(p,b,"a-advanced")
        raise AssertionError("job did not settle")
    try:
        # Separate project/schema for each crash prevents aggregate jobs intercepting later claims.
        for mode in ("checkpoint","ack"):
            childschema=schema+"_"+mode
            cp,cb,cpv,ci=build(childschema,secret,lease_seconds=15);await cp.db.migrate()
            ca=await cp.bootstrap_user("admin@synthetic.invalid",password,"Admin")
            cpr=await cp.bootstrap_project("Crash synthetic",ca)
            login=await cp.login("admin@synthetic.invalid",password);cprin=await cp.authenticate(login.session_token);cc=await cp.authorize(cprin,cpr)
            job=await cp.submit_upload(cc,UploadInput(filename="Crash-safe launch.txt",record_type="report",content=b"Date: 2026-09-01\nThe launch on 2026-10-01 is agreed.\nThe launch budget is EUR 1200."))
            childenv=dict(os.environ,A_LIVE_SECRET=secret)
            for phase in (mode,"resume"):
                logfile=output/(mode+"-"+phase+".json")
                child=await asyncio.create_subprocess_exec(sys.executable,"scripts/evidence/crash_worker.py",childschema,phase,str(logfile),env=childenv)
                code=await child.wait();assert code==(77 if phase==mode else 0),code
                async with cp.db.connection() as conn:
                    row=await (await conn.execute("SELECT data FROM projects WHERE id=%s",(cpr,))).fetchone()
                    saved=[v["batch"] for v in row["data"]["checkpoints"].values()]
                    if phase==mode:
                        before=saved;assert before
                        assert not any(r["published"] for r in row["data"]["records"].values())
                    else:
                        assert saved==before
                        assert row["data"]["jobs"][job.id]["public"]["state"]=="completed"
                        events=json.loads(logfile.read_text())["events"]
                        assert all(e["role"]!="maintenance" for e in events),events
                if phase==mode:await asyncio.sleep(15.1)
            note("CT-17-"+mode,status="PASS",schema=childschema,job_id=job.id,batch_ids=[v["batch_id"] for v in before],resume_provider_events=events)
            await cpv.close();await ci.close()
        first=await p.associate_person(await ctx(),PersonInput(display_name="Alex Reed",kind="employee",contacts=[Contact(kind="email",value="first@synthetic.invalid")]))
        second=await p.associate_person(await ctx(),PersonInput(display_name="Alex Reed",kind="employee",contacts=[Contact(kind="email",value="second@synthetic.invalid")]))
        content=b"Date: 2026-09-01\nAlex Reed first@synthetic.invalid agreed the October launch.\nAlex Reed second@synthetic.invalid owns the November report.\n"
        job=await p.submit_upload(await ctx(),UploadInput(filename="Same-name agreements.txt",record_type="report",content=content))
        state=await drain(job);assert state.state=="completed",state
        docs=(await p.list_documents(await ctx(),PageRequest())).items;doc=docs[0]
        record=(await p.list_records(await ctx(),doc.id,PageRequest())).items[0]
        before=(await p.read_record(await ctx(),record.record_id,PageRequest())).spans
        assert first.id in "\n".join(s.text for s in before) and second.id in "\n".join(s.text for s in before)
        mc=await p.authorize(mp,project);conv=await p.create(mc)
        inp=ChatInput(question="What did Alex Reed first@synthetic.invalid agree?",conversation_id=conv.id,request_id="erase-flight")
        begin=await p.begin_chat(mc,inp);candidate=await b.answer(mc,begin.input)
        erase=await p.erase_person(await ctx(),first.id)
        await reject("write_barrier",p.release_answer(await p.authorize(mp,project),begin.attempt,candidate))
        state=await drain(erase);assert state.state=="completed",state
        current=(await p.read_record(await ctx(),record.record_id,PageRequest())).spans;text="\n".join(s.text for s in current)
        assert "[deleted user] agreed the October launch." in text and second.id in text and first.id not in text
        async with p.db.connection() as conn:
            row=await (await conn.execute("SELECT data FROM projects WHERE id=%s",(project,))).fetchone();s=row["data"]
            assert first.id not in s["people"] and second.id in s["people"]
            assert all("raw" not in d and "raw_filename" not in d for d in s["documents"].values())
            assert not any(first.id in json.dumps(r) for r in s["records"].values())
            entries=list(s["entries"].values());assert entries and all(first.id not in e["person_ids"] for e in entries)
            remote=await index.fetch([e["id"] for e in entries]);assert len(remote)==len(entries)
        note("R-A4-same-name",status="PASS",schema=schema,erasure_job=erase.id,remaining_person=second.id,record_version=record.record_version+1,entry_ids=[e["id"] for e in entries],checks=["exact person","decision retained","other attribution retained","raw copies removed","late chat blocked","real replacement index"])
        # Pause a real Qdrant upsert after durable dispatch, then erase its source identity.
        third=await p.associate_person(await ctx(),PersonInput(display_name="Taylor Green",kind="employee",contacts=[Contact(kind="email",value="third@synthetic.invalid")]))
        latejob=await p.submit_upload(await ctx(),UploadInput(filename="Late writer.txt",record_type="report",content=b"Date: 2026-09-01\nTaylor Green third@synthetic.invalid agreed the pilot on 2026-12-01."))
        original_upsert=index.upsert;dispatched=asyncio.Event();release=asyncio.Event()
        async def paused(entries,vectors):
            dispatched.set();await release.wait();return await original_upsert(entries,vectors)
        index.upsert=paused
        async def run_until_pause():
            while not dispatched.is_set():await run_once(p,b,"a-late-writer")
        writer=asyncio.create_task(run_until_pause())
        await asyncio.wait_for(dispatched.wait(),120)
        lateerase=await p.erase_person(await ctx(),third.id)
        state=await drain(lateerase);assert state.state=="failed" and state.error_code=="index_outcome_unknown",state
        assert (await p.get_status(await ctx())).write_barrier
        note("CT-09-pending",status="PASS",job_id=lateerase.id,stage=state.stage,error_code=state.error_code)
        release.set();await writer;index.upsert=original_upsert
        # A real dependency interruption leaves cleanup failed and its barrier intact.
        await p.retry_job(await ctx(),lateerase.id)
        saved_url=index.url;index.url="http://127.0.0.1:1"
        state=await drain(lateerase);assert state.state=="failed"
        assert (await p.get_status(await ctx())).write_barrier
        index.url=saved_url
        await p.retry_job(await ctx(),lateerase.id)
        state=await drain(lateerase);assert state.state=="completed",state
        assert not (await p.get_status(await ctx())).write_barrier
        async with p.db.connection() as conn:
            row=await (await conn.execute("SELECT data FROM projects WHERE id=%s",(project,))).fetchone()
            jobrow=row["data"]["jobs"][lateerase.id];removed=jobrow["work"]["removal_entry_ids"]
            assert not await index.fetch(removed)
            assert all(op["public"]["state"] not in ("pending","in_flight","unknown") for op in row["data"]["operations"].values())
        note("CT-10/LIVE-08",status="PASS",job_id=lateerase.id,removed_entry_ids=removed,checks=["real paused upsert","barrier before drain","late completion token accepted","real dependency unavailable","same-job retry","obsolete Qdrant points absent"])
    finally:
        await provider.close();await index.close()
asyncio.run(main())
