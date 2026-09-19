"""Verify real repeated-summary embedding replacement and untouched-record isolation."""
import asyncio,argparse,secrets,json
from pathlib import Path
from live_helpers import build
from app.contracts.models import *
from app.evidence.jobs import run_once
async def main():
    a=argparse.ArgumentParser();a.add_argument("--run-id",required=True);args=a.parse_args()
    schema="a_multi_"+args.run_id.lower().replace("-","_");p,b,provider,index=build(schema,secrets.token_hex(32));await p.db.migrate()
    password=secrets.token_urlsafe(24);user=await p.bootstrap_user("admin@synthetic.invalid",password,"Admin");project=await p.bootstrap_project("Multichunk synthetic",user)
    login=await p.login("admin@synthetic.invalid",password);principal=await p.authenticate(login.session_token)
    async def ctx():return await p.authorize(principal,project)
    async def ingest(text,name):
        job=await p.submit_upload(await ctx(),UploadInput(filename=name,record_type="report",content=text.encode()))
        return await work(job)
    async def work(job):
        for _ in range(30):
            result=await p.get_job(await ctx(),job.id)
            if result.state in ("failed","completed"):assert result.state=="completed",result;return result
            await run_once(p,b,"a-multi")
        raise AssertionError("job did not settle")
    async def state():
        async with p.db.connection() as c:return (await (await c.execute("SELECT data FROM projects WHERE id=%s",(project,))).fetchone())["data"]
    try:
        person=await p.associate_person(await ctx(),PersonInput(display_name="Morgan Example",kind="employee",contacts=[Contact(kind="email",value="morgan@synthetic.invalid")]))
        unrelated=await ingest("Date: 2026-09-01\nThe Swedish budget is EUR 500.","Unrelated.txt")
        longtext="Date: 2026-09-01\nMorgan Example morgan@synthetic.invalid agreed the Finnish pilot on 2026-10-01 and owns rollout.\n\n"
        longtext+="\n".join("Operational scope condition "+str(i)+": the Finnish pilot includes only the agreed demonstration stores." for i in range(60))
        changed=await ingest(longtext,"Long attribution.txt")
        before=await state();changed_doc=before["jobs"][changed.id]["work"]["document_ids"][0]
        old=sorted([e for e in before["entries"].values() if e["original_doc_id"]==changed_doc],key=lambda e:before["chunks"][e["chunk_id"]]["ordinal"])
        untouched={eid:e for eid,e in before["entries"].items() if e["original_doc_id"]!=changed_doc}
        assert len(old)>=3
        mc=await ctx();rid=old[0]["record_id"];first=await p.read_record(mc,rid,PageRequest(limit=1));assert first.next_cursor
        seen=list(first.returned_chunk_ids);cursor=first.next_cursor
        while cursor:
            page=await p.read_record(mc,rid,PageRequest(cursor=cursor,limit=1));seen+=page.returned_chunk_ids;cursor=page.next_cursor
        assert len(set(seen))==first.total_chunks
        erase=await p.erase_person(await ctx(),person.id);await work(erase)
        after=await state();new=sorted([e for e in after["entries"].values() if e["original_doc_id"]==changed_doc],key=lambda e:after["chunks"][e["chunk_id"]]["ordinal"])
        assert len(new)==len(old) and all(a["input_hash"]!=z["input_hash"] for a,z in zip(old,new,strict=True))
        assert all(after["entries"].get(eid)==entry for eid,entry in untouched.items())
        assert not await index.fetch([e["id"] for e in old])
        assert len(await index.fetch([e["id"] for e in new]))==len(new)
        try:await p.read_record(await ctx(),rid,PageRequest(cursor=first.next_cursor,limit=1))
        except Exception as error:assert getattr(error,"code",None)=="stale_cursor"
        else:raise AssertionError("stale cursor accepted")
        result=dict(status="PASS",schema=schema,job_id=erase.id,old_entries=[e["id"] for e in old],new_entries=[e["id"] for e in new],untouched_entries=list(untouched),checks=["full ordered chunk pagination","stale cursor denied","every repeated-summary hash changed","real replacement embeddings","old points absent","unrelated entry payload unchanged"])
        out=Path("artifacts/evidence")/args.run_id;out.mkdir(parents=True,exist_ok=True);(out/"multichunk.json").write_text(json.dumps(result,indent=2));print(json.dumps(result))
    finally:await provider.close();await index.close();await p.db.close()
asyncio.run(main())
