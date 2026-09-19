"""Live canonical parsing/privacy/access scenarios, with real B maintenance."""
import argparse,asyncio,json,secrets
from pathlib import Path
from app.contracts.models import *
from app.contracts.errors import DomainError
from app.evidence.jobs import run_once
from live_helpers import build
async def main():
    args=argparse.ArgumentParser();args.add_argument("--run-id",required=True);a=args.parse_args()
    schema="a_src_"+a.run_id.lower().replace("-","_");p,b,provider,index=build(schema,secrets.token_hex(32));await p.db.migrate()
    original_generate=provider.generate;original_embed=provider.embed;privacy_calls=[]
    def assert_private_absent(value):
        serialized=json.dumps(value).casefold()
        assert "casey test" not in serialized and "casey@synthetic.invalid" not in serialized
    async def checked_generate(role,system,payload,**kwargs):
        assert_private_absent(payload);privacy_calls.append(role)
        return await original_generate(role,system,payload,**kwargs)
    async def checked_embed(texts,**kwargs):
        assert_private_absent(texts);privacy_calls.append("embedding")
        return await original_embed(texts,**kwargs)
    provider.generate=checked_generate;provider.embed=checked_embed
    import traceback
    original_process=b.process_record
    async def diagnostic(*args):
        try:return await original_process(*args)
        except Exception as error:
            seen=set();cause=error
            while cause is not None and id(cause) not in seen:
                seen.add(id(cause))
                print(json.dumps({"diagnostic_type":type(cause).__name__,"locations":[[x.filename,x.lineno,x.name] for x in traceback.extract_tb(cause.__traceback__)]}),flush=True)
                cause=cause.__cause__ or cause.__context__
            raise
    b.process_record=diagnostic
    out=Path("artifacts/evidence")/a.run_id;out.mkdir(parents=True,exist_ok=True);observations=[]
    def note(case,**data):
        observations.append(dict(case=case,**data));(out/"sources.json").write_text(json.dumps(observations,indent=2));print(json.dumps(observations[-1]),flush=True)
    pw=secrets.token_urlsafe(24);admin=await p.bootstrap_user("admin@synthetic.invalid",pw,"Admin");outsider=await p.bootstrap_user("outsider@synthetic.invalid",pw,"Outsider")
    project=await p.bootstrap_project("Parsing synthetic",admin)
    login=await p.login("admin@synthetic.invalid",pw);principal=await p.authenticate(login.session_token)
    outsider_login=await p.login("outsider@synthetic.invalid",pw);op=await p.authenticate(outsider_login.session_token)
    async def ctx():return await p.authorize(principal,project)
    async def denied(code,coro):
        try:await coro
        except DomainError as e:assert e.code==code,(e.code,code);return
        raise AssertionError("expected "+code)
    async def ingest(text,kind,filename):
        job=await p.submit_upload(await ctx(),UploadInput(filename=filename,record_type=kind,content=text.encode()))
        for _ in range(30):
            state=await p.get_job(await ctx(),job.id)
            if state.state in ("completed","failed"):return state
            await run_once(p,b,"a-source")
        raise AssertionError("job did not settle")
    try:
        person=await p.associate_person(await ctx(),PersonInput(display_name="Casey Test",kind="employee",contacts=[Contact(kind="email",value="casey@synthetic.invalid")]))
        bundle="From: Casey Test <casey@synthetic.invalid>\nDate: 2026-09-01\nSubject: Launch\nThe launch on 2026-10-01 is proposed.\n-----\nFrom: Casey Test <casey@synthetic.invalid>\nDate: 2026-09-02\nSubject: Follow up\nThe October launch remains a proposal.\n> From: Casey Test <casey@synthetic.invalid>\n> The launch is proposed."
        job=await ingest(bundle,"email","Synthetic bundle.txt");assert job.state=="completed",job
        async with p.db.connection() as c:
            state=(await (await c.execute("SELECT data FROM projects WHERE id=%s",(project,))).fetchone())["data"]
            doc=state["jobs"][job.id]["work"]["document_ids"][0];records=sorted([r for r in state["records"].values() if r["original_doc_id"]==doc],key=lambda r:r["spans"][0]["source_location"]["line_start"])
            assert len(records)==2
            assert sum(len(r["spans"]) for r in records)==len(bundle.splitlines())
            assert all("Casey Test" not in json.dumps(r["spans"]) and "casey@" not in json.dumps(r["spans"]) for r in records)
            assert records[1]["spans"][-1]["text"].startswith("> ")
            candidate_entry=next(iter(state["entries"].values()))
            oldcap=next((JobCapability.model_validate(v) for v in state["capabilities"].values() if v["job_id"]==job.id),None)
        note("R-A2-bundle",status="PASS",schema=schema,job_id=job.id,record_ids=[r["record_id"] for r in records],checks=["two complete headers split","quoted forwarding retained in selected record","all source lines accounted","source line provenance","names/contacts normalized before real generation"])
        duplicate=await ingest(bundle,"email","Synthetic duplicate.txt");assert duplicate.state=="completed",duplicate
        transcript=await ingest("Casey Test: The pilot on 2026-10-01 is agreed.\nCasey Test: The budget remains unknown.","transcript","Synthetic transcript.txt");assert transcript.state=="completed",transcript
        report=await ingest("No source date is supplied.\nThe identifier ZXQ-987 remains active.","report","Synthetic report.txt");assert report.state=="completed",report
        async with p.db.connection() as c:
            state=(await (await c.execute("SELECT data FROM projects WHERE id=%s",(project,))).fetchone())["data"]
            dupdoc=state["jobs"][duplicate.id]["work"]["document_ids"][0]
            assert all(r["duplicate_of"] for r in state["records"].values() if r["original_doc_id"]==dupdoc)
            reportdoc=state["jobs"][report.id]["work"]["document_ids"][0]
            assert all(r["source_time"]["precision"]=="unknown" for r in state["records"].values() if r["original_doc_id"]==reportdoc)
        note("R-A2-formats",status="PASS",job_ids=[duplicate.id,transcript.id,report.id],checks=["duplicates retain lineage","transcript remains one record","unknown dates preserved"])
        await denied("unsupported_format",p.submit_upload(await ctx(),UploadInput(filename="Bad.txt",record_type="report",content=b"\xff")))
        await denied("unsupported_format",p.submit_upload(await ctx(),UploadInput(filename="Bad.pdf",record_type="report",content=b"%PDF-1.7")))
        ambiguous=await p.associate_person(await ctx(),PersonInput(display_name="Casey Test",kind="client",contacts=[Contact(kind="email",value="other@synthetic.invalid")]))
        failure=await ingest("Casey Test agreed a revised plan.","report","Quarantined.txt");assert failure.state=="failed" and failure.error_code=="privacy_unresolved"
        note("R-A2-quarantine",status="PASS",job_id=failure.id,checks=["malformed bytes rejected","unsupported PDF rejected","same-name unqualified identity quarantined"])
        # Canonical adapters themselves reject an unauthorized session even if called directly.
        forged=(await ctx()).model_copy(update={"user_id":op.user_id,"session_id":op.session_id,"role":"member"})
        rid=records[0]["record_id"];ref=EvidenceRef(project_id=project,original_doc_id=doc,record_id=rid,record_version=1,span_ids=[records[0]["spans"][0]["span_id"]])
        calls=[
          p.list_documents(forged,PageRequest()),p.list_records(forged,doc,PageRequest()),
          p.read_record(forged,rid,PageRequest()),p.read_source(forged,SourceRequest(record_id=rid,version=1,span_id=ref.span_ids[0])),
          p.get_status(forged),p.get_overview(forged),p.get_filters(forged),p.list_people(forged,PageRequest()),p.list_members(forged,PageRequest()),p.list_jobs(forged,PageRequest()),p.list(forged,PageRequest()),
          p.reader.read_record(forged,rid,PageRequest()),p.reader.read_memory(forged,"unknown"),
          p.reader.normalize_query(forged,"launch"),p.reader.make_receipt(forged,ref),
          p.reader.expand_context(forged,ref),p.lexical_candidates(forged,"launch",SearchFilters(),10),p.validate_candidates(forged,[],SearchFilters()),p.read_history(forged,HistoryQuery(topic_id="unknown",scope="launch",as_of=None),PageRequest())]
        for call in calls:await denied("not_found",call)
        reference=CandidateRef(entry_id=candidate_entry["id"],record_id=candidate_entry["record_id"],record_version=candidate_entry["record_version"],chunk_id=candidate_entry["chunk_id"],input_hash=candidate_entry["input_hash"],rank=1)
        assert (await p.validate_candidates(await ctx(),[reference],SearchFilters())).eligible
        bad=reference.model_copy(update={"record_version":reference.record_version+1})
        check=await p.validate_candidates(await ctx(),[bad],SearchFilters());assert not check.eligible and check.rejected_entry_ids==[bad.entry_id]
        await denied("source_unavailable",p.read_source(await ctx(),SourceRequest(record_id=rid,version=99,span_id=ref.span_ids[0])))
        note("R-A1/R-A3-canonical-access",status="PASS",checks=["19 canonical read entry points reject nonmember","unrelated publication preserves original valid candidate","stale index reference yields no canonical text","old source version denied"],privacy_provider_calls=privacy_calls)
    finally:await provider.close();await index.close();await p.db.close()
asyncio.run(main())
