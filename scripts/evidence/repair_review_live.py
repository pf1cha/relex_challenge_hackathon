"""Focused real-service repair probes; synthetic retained review resources only."""
import asyncio,json,os,secrets,subprocess,sys,socket
from pathlib import Path
from dotenv import load_dotenv
from psycopg.types.json import Jsonb
from app.contracts.models import *
from app.evidence.jobs import run_once
from app.evidence.service import iso
from live_helpers import build
import httpx

load_dotenv(override=False)
os.environ.setdefault("RELEX_DATABASE_URL","postgresql://relex_dev@127.0.0.1:15432/postgres")
os.environ.setdefault("RELEX_QDRANT_URL","http://127.0.0.1:16333")
output=Path("artifacts/evidence/repair_review_0919");output.mkdir(parents=True,exist_ok=True)
observations=[]
def note(case,**data):
    observations.append(dict(case=case,**data))
    (output/"repair.json").write_text(json.dumps(observations,indent=2))
    print(json.dumps(observations[-1]),flush=True)

async def state(p,project):
    async with p.db.connection() as c:
        return (await (await c.execute("SELECT data FROM projects WHERE id=%s",(project,))).fetchone())["data"]

async def drain(p,b,principal,project,job_id):
    for _ in range(30):
        job=await p.get_job(await p.authorize(principal,project),job_id)
        if job.state in ("completed","failed"):return job
        await run_once(p,b,"repair-a")
    raise AssertionError("job did not settle")

async def new_admin(p,project=None):
    password=secrets.token_urlsafe(24);email="repair-"+secrets.token_hex(4)+"@synthetic.invalid"
    user=await p.bootstrap_user(email,password,"Synthetic repair admin")
    if project:
        # Retained reviewer credentials were deliberately not retained. Bootstrap
        # access to this synthetic review fixture; do not alter content/jobs.
        async with p.db.connection() as c:
            row=await (await c.execute("SELECT data FROM projects WHERE id=%s FOR UPDATE",(project,))).fetchone()
            s=row["data"];s["members"][user]=dict(role="admin",revision=1,granted_at=iso())
            await c.execute("UPDATE projects SET data=%s WHERE id=%s",(Jsonb(s),project))
    else:project=await p.bootstrap_project("Repair synthetic",user)
    login=await p.login(email,password)
    return await p.authenticate(login.session_token),project

async def main():
    resources=[]
    try:
        p,b,pv,idx=build("a_repair_unknown_0919",secrets.token_hex(32));resources.append((p,pv,idx))
        await p.db.migrate();principal,project=await new_admin(p)
        async def ctx():return await p.authorize(principal,project)
        job=await p.submit_upload(await ctx(),UploadInput(filename="ownership.txt",record_type="report",content=b"Date: 2026-09-01\nThe owner is Alice Example.\nThe pilot launch is agreed for 2026-10-01."))
        result=await drain(p,b,principal,project,job.id)
        assert result.state=="failed" and result.error_code=="privacy_unresolved",result
        assert not pv.events
        s=await state(p,project);assert not any(r["published"] for r in s["records"].values())
        assert all(d["processing_state"]=="failed" for d in s["documents"].values())
        person=await p.associate_person(await ctx(),PersonInput(display_name="Alice Example",kind="employee",contacts=[]))
        await p.retry_job(await ctx(),job.id);result=await drain(p,b,principal,project,job.id);assert result.state=="completed",result
        s=await state(p,project);assert all("Alice Example" not in json.dumps(r["spans"]) for r in s["records"].values())
        note("R-A2-unknown-owner",status="PASS",schema=p.db.schema,job_id=job.id,checks=["unresolved ownership quarantined","zero downstream calls before association","same job retries after association","published canonical source uses opaque identity"],events=pv.events)

        # Repair retained material actually published by the review, without editing
        # the affected record, old erasure job or external index.
        p,b,pv,idx=build("review_privacy_0919",secrets.token_hex(32));resources.append((p,pv,idx))
        principal,project=await new_admin(p,"06e769b6-d2c4-41f7-88bf-ad4f7ef5eee2")
        async def ctx():return await p.authorize(principal,project)
        before=await state(p,project);rid="1b752043-38bf-4f10-9702-66b87002b82b"
        assert "Alice Example" in json.dumps(before["records"][rid]["spans"])
        old_ids=before["records"][rid]["entry_ids"]
        person=await p.associate_person(await ctx(),PersonInput(display_name="Alice Example",kind="employee",contacts=[]))
        erase=await p.erase_person(await ctx(),person.id)
        barrier=await p.get_status(await ctx());assert barrier.write_barrier
        result=await drain(p,b,principal,project,erase.id);assert result.state=="completed",result
        after=await state(p,project);assert "Alice Example" not in json.dumps(after)
        assert "[deleted user]" in json.dumps(after["records"][rid]["spans"])
        assert not await idx.fetch(old_ids)
        assert not after["write_barrier"]
        entries=after["records"][rid]["entry_ids"];assert entries and await idx.verify([IndexEntry.model_validate(after["entries"][i]) for i in entries])
        note("R-A4-retained-original-alias",status="PASS",schema=p.db.schema,job_id=erase.id,old_job="93c51a98-997f-4b9c-bd3f-2e3d2947af4c",record_id=rid,removed_entry_ids=old_ids,current_entry_ids=entries,bootstrap="New synthetic admin membership; reviewer password was not retained. Source/jobs/index unmodified before ordinary association and erasure.",checks=["original alias inventoried without original opaque mapping","all persisted controlled data lacks original name","decision retained with deleted attribution","real obsolete points absent","replacement real points verified"],events=pv.events)

        # Retained unrelated upload must recover after another source deactivation.
        p,b,pv,idx=build("review_jobs_0919",secrets.token_hex(32));resources.append((p,pv,idx))
        principal,project=await new_admin(p,"80efe0fd-6b5a-4467-ba22-8b4cb6e11181")
        old="1540a08c-2aef-4a0d-8d8d-716e355fa68a"
        before=await state(p,project);did=before["jobs"][old]["work"]["document_ids"][0]
        assert before["jobs"][old]["public"]["error_code"]=="superseded"
        for _ in range(20):
            await run_once(p,b,"repair-unrelated")
            current=await state(p,project)
            replacement=current["documents"][did]["latest_job_id"]
            if replacement!=old and current["jobs"][replacement]["public"]["state"] in ("completed","failed"):break
        assert replacement!=old and current["jobs"][replacement]["public"]["state"]=="completed",current["jobs"][replacement]["public"]
        assert current["documents"][did]["processing_state"]=="completed"
        r=next(r for r in current["records"].values() if r["original_doc_id"]==did)
        assert await idx.verify([IndexEntry.model_validate(current["entries"][i]) for i in r["entry_ids"]])
        note("R-A2-R-A3-retained-unrelated",status="PASS",schema=p.db.schema,old_job=old,replacement_job=replacement,document_id=did,checks=["old accepted work recovered","old job remains fenced","document state completed","real replacement index verified"],events=pv.events)

        # The existing stranded cleanup uses its original authenticated app and job.
        cfg=json.loads(Path(".runtime/c_c_late2/private.json").read_text())
        p,b,pv,idx=build(cfg["schema"],cfg["secret"]);resources.append((p,pv,idx))
        job_id="8f71c03e-2efa-44ef-9d38-c92d8236af53";project=cfg["project_id"]
        before=await state(p,project);inventory=before["jobs"][job_id]["work"]
        assert before["jobs"][job_id]["public"]["state"]=="failed" and before["write_barrier"]
        with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
        origin="http://127.0.0.1:"+str(port)
        env=dict(os.environ,RELEX_DATABASE_SCHEMA=cfg["schema"],RELEX_QDRANT_COLLECTION=cfg["collection"],RELEX_SESSION_SECRET=cfg["secret"],RELEX_LOOPBACK_HTTP="1",RELEX_TRUSTED_ORIGINS=origin,RELEX_REQUEST_TIMEOUT_SECONDS="300")
        log=(output/"retained-http.log").open("a")
        proc=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:production_app","--factory","--host","127.0.0.1","--port",str(port),"--no-access-log"],env=env,stdout=log,stderr=log)
        try:
            async with httpx.AsyncClient(base_url=origin,timeout=30) as client:
                for _ in range(50):
                    try:
                        if (await client.get("/health")).status_code==200:break
                    except httpx.HTTPError:pass
                    await asyncio.sleep(.1)
                response=await client.post("/api/login",headers={"Origin":origin},json={"email":cfg["admin_email"],"password":cfg["password"]});assert response.status_code==200
                headers={"Origin":origin,"X-CSRF-Token":response.json()["csrf_token"]}
                endpoint="/api/projects/"+project+"/jobs/"+job_id
                response=await client.get(endpoint);assert response.status_code==200 and response.json()["retryable"]
                response=await client.post(endpoint+"/retry",headers=headers);assert response.status_code==200,response.text
                queued=await state(p,project);assert queued["jobs"][job_id]["work"]==inventory and queued["write_barrier"]
                for _ in range(20):
                    await run_once(p,b,"repair-retained")
                    after=await state(p,project)
                    if after["jobs"][job_id]["public"]["state"] in ("failed","completed"):break
                assert after["jobs"][job_id]["public"]["state"]=="completed",after["jobs"][job_id]["public"]
                assert after["jobs"][job_id]["work"]==inventory and not after["write_barrier"]
                assert not await idx.fetch(inventory["removal_entry_ids"])
                response=await client.get(endpoint);assert response.json()["state"]=="completed"
                note("R-A4-R-C4-retained-failure-retry",status="PASS",schema=p.db.schema,job_id=job_id,http_port=port,http_pid=proc.pid,retry_http_status=200,checks=["original retained failed job","authenticated GET exposes retry","authenticated POST accepts same job","durable inventory unchanged","barrier until validated completion","real obsolete Qdrant points absent","HTTP completed status"],events=pv.events)
        finally:
            proc.terminate();proc.wait(timeout=15);log.close()
    finally:
        for p,pv,idx in resources:
            await pv.close();await idx.close();await p.db.close()
asyncio.run(main())

