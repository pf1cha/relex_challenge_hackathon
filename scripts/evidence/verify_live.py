"""Real-service A acceptance driver. Inputs synthetic; provider/index results are real."""
import argparse, asyncio, json, os, re, secrets, sys
from pathlib import Path
from datetime import datetime, timezone
from app.contracts.models import *
from app.contracts.errors import DomainError
from app.evidence.postgres import Postgres
from app.evidence.service import EvidencePlatform
from app.evidence.jobs import run_once

def env_file():
    from dotenv import dotenv_values
    return {**{k:v for k,v in dotenv_values(".env").items() if v is not None},**os.environ}

async def main():
    parser=argparse.ArgumentParser();parser.add_argument("--run-id",required=True);parser.add_argument("--component-only",action="store_true")
    args=parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}",args.run_id):raise SystemExit("invalid run id")
    env=env_file();schema="a_live_"+args.run_id.lower().replace("-","_")
    output=Path("artifacts/evidence")/args.run_id;output.mkdir(parents=True,exist_ok=True)
    events=[]
    def report(case,status,**details):
        event=dict(case=case,status=status,at=datetime.now(timezone.utc).isoformat(),**details);events.append(event)
        (output/"observations.json").write_text(json.dumps(events,indent=2));print(json.dumps(event),flush=True)
    async def rejected(code,call):
        try:await call
        except DomainError as exc:assert exc.code==code,(exc.code,code);return
        raise AssertionError("expected "+code)
    dsn=env.get("RELEX_DATABASE_URL","")
    # Explicit local override supports native PG environment variables without a hosted DB.
    if os.environ.get("PGHOST"):dsn=""
    db=Postgres(dsn,schema)
    try:await db.migrate();await db.migrate()
    except Exception:
        report("R-A1","BLOCKED",reason="native PostgreSQL unavailable");return 2
    p=EvidencePlatform(db,secrets.token_hex(32))
    password=secrets.token_urlsafe(24)
    admin=await p.bootstrap_user("admin@synthetic.invalid",password,"Synthetic Admin")
    member=await p.bootstrap_user("member@synthetic.invalid",password,"Synthetic Member")
    outsider=await p.bootstrap_user("outsider@synthetic.invalid",password,"Synthetic Outsider")
    project=await p.bootstrap_project("Synthetic A "+args.run_id,admin)
    project2=await p.bootstrap_project("Synthetic other",outsider)
    async def login(email):
        result=await p.login(email,password);return await p.authenticate(result.session_token)
    ap=await login("admin@synthetic.invalid");mp=await login("member@synthetic.invalid");op=await login("outsider@synthetic.invalid")
    async def actx():return await p.authorize(ap,project)
    await p.set_member(await actx(),member,"member")
    mc=await p.authorize(mp,project)
    await rejected("not_found",p.authorize(op,project))
    await rejected("forbidden",p.list_people(mc,PageRequest()))
    await rejected("last_admin",p.remove_member(await actx(),admin))
    await rejected("unauthenticated",p.login("admin@synthetic.invalid","incorrect"))
    assert len((await p.list_projects(mp,PageRequest())).items)==1
    test_session=await login("member@synthetic.invalid");await p.logout(test_session)
    await rejected("unauthenticated",p.me(test_session))
    # Native transaction state survives adapter recreation.
    p2=EvidencePlatform(Postgres(dsn,schema),p.secret)
    assert (await p2.get_status(await actx())).eligible_records==0
    await p2.db.close()
    report("R-A1","PASS",schema=schema,project_id=project,other_project_id=project2,checks=["repeat migration","real login","admin/member/outsider","last admin","project filter","logout","adapter restart"])
    if args.component_only:
        report("R-A2/R-A3/R-A4","BLOCKED",reason="component-only development mode; no substitute acceptance")
        return 0
    try:
        from app.intelligence.providers import ModelProvider,ProviderSettings
        from app.intelligence.qdrant import QdrantIndex
        from app.intelligence.service import Intelligence
    except ImportError:
        report("R-A2/R-A3/R-A4","BLOCKED",reason="real B adapter absent");return 2
    provider=ModelProvider(ProviderSettings(base_url=env.get("RELEX_MODEL_BASE_URL",""),model=env.get("RELEX_MODEL_NAME",""),api_key=(env.get("RELEX_MODEL_API_KEY") or env.get("OPENAI_API_KEY","")),embedding_base_url=env.get("RELEX_EMBEDDING_BASE_URL",""),embedding_model=env.get("RELEX_EMBEDDING_MODEL",""),embedding_api_key=(env.get("RELEX_EMBEDDING_API_KEY") or env.get("OPENAI_API_KEY","")),timeout_seconds=120))
    index=QdrantIndex(env.get("RELEX_QDRANT_URL","http://127.0.0.1:16333"),schema,env.get("RELEX_QDRANT_API_KEY",""))
    limits=RuntimeLimits(answer_search_rounds=3,repair_search_rounds=1,reviewer_passes=2,reviewer_search_rounds=3,tool_calls_per_phase=24,pages_per_phase=24,source_tokens_per_phase=24000,request_deadline_seconds=120)
    b=Intelligence(p.reader,p.retrieval,p.artifacts,p.ledger,provider,index,limits,p.secret)
    async def work(job):
        for _ in range(20):
            current=await p.get_job(await actx(),job.id)
            if current.state in ("failed","completed"):return current
            assert await run_once(p,b,"a-live-"+args.run_id)
        raise AssertionError("job did not settle")
    try:
        upload=await p.submit_upload(await actx(),UploadInput(filename="Synthetic launch.txt",record_type="report",content=b"Date: 2026-09-01\nThe project launch in October is agreed.\nThe agreed budget is EUR 1200.\n"))
        job=await work(upload)
        if job.state!="completed":
            report("R-A2","FAIL",job=dump_job(job));return 1
        docs=await p.list_documents(await p.authorize(mp,project),PageRequest());assert len(docs.items)==1
        records=await p.list_records(await p.authorize(mp,project),docs.items[0].id,PageRequest())
        record=records.items[0];page=await p.read_record(await p.authorize(mp,project),record.record_id,PageRequest(limit=1))
        assert page.spans and page.complete
        report("R-A2","PASS",job_id=job.id,record_id=record.record_id,record_version=record.record_version,chunk_ids=page.returned_chunk_ids,provider_events=provider.events)
        mc=await p.authorize(mp,project);conv=await p.create(mc)
        question=ChatInput(question="What launch date is agreed?",conversation_id=conv.id,request_id="a-real-chat")
        begin=await p.begin_chat(mc,question);candidate=await b.answer(mc,begin.input)
        assert candidate.claims,"real B returned no supported claim"
        altered=candidate.model_copy(deep=True);altered.candidate_digest="0"*64
        await rejected("contract_violation",p.release_answer(mc,begin.attempt,altered))
        answer=await p.release_answer(mc,begin.attempt,candidate)
        replay=await p.begin_chat(mc,question);assert replay.state=="replay" and replay.answer.id==answer.id
        await rejected("idempotency_conflict",p.begin_chat(mc,question.model_copy(update={"question":"Different question"})))
        await rejected("not_found",p.messages(await actx(),conv.id,PageRequest()))
        for receipt in answer.receipts:
            got=await p.get_receipt(mc,answer.id,receipt.id);assert got.quote==receipt.quote
        report("R-A3","PASS",answer_id=answer.id,receipt_ids=[r.id for r in answer.receipts],checks=["real B review and SQL release","tampered digest denied","owner denial","idempotent replay","changed-input conflict","exact receipt"])
        # Reuse a candidate from actual B review for focused release-only mutation races.
        begin2=await p.begin_chat(mc,question.model_copy(update={"request_id":"logout-flight"}))
        await p.logout(mp)
        await rejected("unauthenticated",p.release_answer(mc,begin2.attempt,candidate))
        mp=await login("member@synthetic.invalid");mc=await p.authorize(mp,project)
        begin3=await p.begin_chat(mc,question.model_copy(update={"request_id":"revoke-flight"}))
        await p.remove_member(await actx(),member)
        await rejected("not_found",p.release_answer(mc,begin3.attempt,candidate))
        await p.set_member(await actx(),member,"member")
        await rejected("evidence_changed",p.release_answer(mc,begin3.attempt,candidate))
        mc=await p.authorize(mp,project)
        begin4=await p.begin_chat(mc,question.model_copy(update={"request_id":"deactivate-flight"}))
        deactivate=await p.mutate_document(await actx(),docs.items[0].id,"deactivate")
        await rejected("evidence_changed",p.release_answer(mc,begin4.attempt,candidate))
        report("R-A3-inflight","PASS",checks=["logout denies release","revocation denies release","regrant epoch denies old context","deactivation denies release"])
        await rejected("source_unavailable",p.get_receipt(await p.authorize(mp,project),answer.id,answer.receipts[0].id))
        current=await work(deactivate);assert current.state=="completed",dump_job(current)
        assert not (await p.list_documents(await p.authorize(mp,project),PageRequest())).items
        report("R-A4-deactivate","PASS",job_id=current.id)
        activate=await p.mutate_document(await actx(),docs.items[0].id,"activate");current=await work(activate);assert current.state=="completed",dump_job(current)
        assert (await p.list_documents(await p.authorize(mp,project),PageRequest())).items
        deletion=await p.mutate_document(await actx(),docs.items[0].id,"delete");current=await work(deletion);assert current.state=="completed",dump_job(current)
        assert not (await p.list_documents(await actx(),PageRequest())).items
        report("R-A4-document-delete","PASS",job_id=current.id,barrier=(await p.get_status(await actx())).write_barrier)
        for script,suffix in (("advanced_live.py","_adv"),("source_live.py","_src"),("capability_live.py","_cap"),("multichunk_live.py","_multi")):
            process=await asyncio.create_subprocess_exec(sys.executable,"scripts/evidence/"+script,"--run-id",args.run_id+suffix)
            code=await process.wait()
            if code:
                report("R-A2/R-A4-extended","FAIL",script=script,exit_status=code)
                return code
        report("R-A1/R-A2/R-A3/R-A4","PASS",extended_runs=[args.run_id+suffix for suffix in ("_adv","_src","_cap","_multi")])
        return 0
    except DomainError as exc:
        report("R-A2/R-A3/R-A4","FAIL",code=exc.code);return 1
    finally:
        await provider.close();await index.close();await p.db.close()
def dump_job(job):return job.model_dump(mode="json")
if __name__=="__main__":
    raise SystemExit(asyncio.run(main()))
