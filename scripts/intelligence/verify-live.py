"""Actual B workflow with A PostgreSQL repositories, real models and Qdrant.

Uses a fresh isolated schema and collection. No contract-test/fixture-service imports.
Resources are retained for independent inspection and restart probes.
"""
import argparse,asyncio,json,os,re,secrets,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from dotenv import dotenv_values
from app.contracts.models import *
from app.contracts.errors import DomainError
from app.intelligence.providers import ModelProvider,ProviderSettings,ProviderFailure
from app.intelligence.qdrant import QdrantIndex,IndexFailure
from app.intelligence.service import Intelligence

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);parser.add_argument('--case',action='append');args=parser.parse_args()
    if not re.fullmatch('[a-z][a-z0-9_]{0,35}',args.run_id):raise SystemExit('run-id: lowercase letters, digits, underscores; start with a letter, max 36')
    cfg={**dotenv_values('.env'),**os.environ};folder=Path('scripts/intelligence/runs')/args.run_id
    folder.mkdir(parents=True,exist_ok=True)
    report={'run_id':args.run_id,'schema':'b_live_'+args.run_id,'collection':'b_live_'+args.run_id,'started_at':datetime.now(timezone.utc).isoformat(),
      'revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'contract_revision':5,'substitutes':[],
      'cases':[],'requirements':{r:'BLOCKED' for r in ['R-B1','R-B2','R-B3','R-B4','R-S']}}
    def save(): (folder/'live.json').write_text(json.dumps(report,indent=2))
    provider=index=None
    try:
        from app.evidence.postgres import Postgres
        from app.evidence.service import EvidencePlatform
        from app.evidence.jobs import run_once
        dsn=cfg.get('RELEX_LIVE_DATABASE_URL') or cfg.get('RELEX_DATABASE_URL')
        if not dsn:raise RuntimeError('Missing RELEX_LIVE_DATABASE_URL / RELEX_DATABASE_URL')
        db=Postgres(dsn,report['schema']);await db.migrate()
        secret_file=folder/'secret'
        if not secret_file.exists():secret_file.write_text(secrets.token_hex(32));secret_file.chmod(0o600)
        platform=EvidencePlatform(db,secret_file.read_text(),request_deadline_seconds=240)
        provider=ModelProvider(ProviderSettings(base_url=cfg.get('RELEX_MODEL_BASE_URL') or '',model=cfg.get('RELEX_MODEL_NAME') or '',api_key=cfg.get('RELEX_MODEL_API_KEY') or cfg.get('OPENAI_API_KEY') or '',embedding_base_url=cfg.get('RELEX_EMBEDDING_BASE_URL') or '',embedding_model=cfg.get('RELEX_EMBEDDING_MODEL') or '',embedding_api_key=cfg.get('RELEX_EMBEDDING_API_KEY') or cfg.get('OPENAI_API_KEY') or ''))
        index=QdrantIndex(cfg.get('RELEX_QDRANT_URL') or 'http://127.0.0.1:16333',report['collection'],cfg.get('RELEX_QDRANT_API_KEY') or '')
        limits=RuntimeLimits(answer_search_rounds=3,repair_search_rounds=1,reviewer_passes=2,reviewer_search_rounds=3,tool_calls_per_phase=50,pages_per_phase=40,source_tokens_per_phase=120000,request_deadline_seconds=240)
        service=Intelligence(platform.reader,platform.retrieval,platform.artifacts,platform.ledger,provider,index,limits,secret_file.read_bytes())
        cases=json.loads(Path('backend/tests/intelligence/cases.json').read_text())
        for case in cases:
            if args.case and case['id'] not in args.case:continue
            observed={'id':case['id'],'status':'RUNNING','expected':case['expected'],'prohibited':case['prohibited']};report['cases'].append(observed);save()
            password=secrets.token_urlsafe(24);email=case['id'].lower()+'@'+args.run_id+'.invalid'
            uid=await platform.bootstrap_user(email,password,'Synthetic Member')
            pid=await platform.bootstrap_project('Synthetic '+case['id'],uid)
            login=await platform.login(email,password);principal=await platform.authenticate(login.session_token)
            observed['project_id']=pid;observed['jobs']=[]
            for n,text in enumerate(case['records']):
                ctx=await platform.authorize(principal,pid)
                job=await platform.submit_upload(ctx,UploadInput(filename='synthetic-'+str(n)+'.txt',record_type='report',content=text.encode()))
                observed['jobs'].append(job.id)
                for _ in range(30):
                    await run_once(platform,service,'b-live-'+args.run_id)
                    ctx=await platform.authorize(principal,pid);state=await platform.get_job(ctx,job.id)
                    if state.state in ['completed','failed']:break
                if state.state!='completed':raise RuntimeError('Ingestion '+state.state+': '+str(state.error_code))
            # Drain aggregates through the same real durable runner.
            for _ in range(20):
                if not await run_once(platform,service,'b-live-'+args.run_id):break
            ctx=await platform.authorize(principal,pid)
            documents=await platform.list_documents(ctx,PageRequest(limit=100));observed['documents']=[d.model_dump(mode='json') for d in documents.items]
            search=await service.search_memory(ctx,SearchInput(query=case['question'],filters=SearchFilters(),page=PageRequest(limit=100)))
            observed['search']=search.model_dump(mode='json')
            conversation=await platform.create(ctx)
            chat=ChatInput(question=case['question'],conversation_id=conversation.id,request_id=secrets.token_hex(16))
            begin=await platform.begin_chat(ctx,chat)
            candidate=await service.answer(ctx,begin.input)
            answer=await platform.release_answer(ctx,begin.attempt,candidate)
            # Construct a fresh real adapter to read persisted state (not an in-memory return).
            restarted=EvidencePlatform(Postgres(dsn,report['schema']),secret_file.read_text())
            reread=await restarted.get_answer(ctx,answer.id)
            assert reread==answer
            for receipt in answer.receipts:
                canonical=await restarted.reader.make_receipt(ctx,receipt.evidence_ref)
                assert canonical.quote==receipt.quote
            replay=await platform.begin_chat(ctx,chat);assert replay.state=='replay' and replay.answer.id==answer.id
            try:
                await platform.begin_chat(ctx,chat.model_copy(update={'question':case['question']+' changed'}))
                raise AssertionError('different input accepted under same request ID')
            except DomainError as exc:assert exc.code=='idempotency_conflict'
            observed.update(status='EXECUTED_SEMANTIC_REVIEW_REQUIRED',answer=answer.model_dump(mode='json'),candidate=candidate.model_dump(mode='json'),persisted_restart_equal=True,receipt_quotes_equal=True,idempotent_replay=True)
            save()
        report['provider_events']=provider.events;report['safe_traces']=service.traces
        report['status']='EXECUTED_PENDING_ACCEPTANCE_REVIEW'
        report['remaining']=['Inspect semantic expected/prohibited assertions per case','LIVE-03 all filters, long-record pagination and stale payloads','LIVE-06 interrupted checkpoint restart','LIVE-07/08 actual lifecycle late-writer probes','LIVE-11 adversarial reviewer/provider/budget probes','LIVE-10 two isolated runs and G4 concurrency','C browser G1-G4']
        save();print(json.dumps({'status':report['status'],'report':str(folder/'live.json'),'cases':len(report['cases'])}))
        # Partial live execution is deliberately nonzero; never represent a grouped session as full acceptance.
        return 3
    except Exception as exc:
        safe=str(exc) if isinstance(exc,(DomainError,ProviderFailure,IndexFailure,RuntimeError,AssertionError)) else type(exc).__name__
        report['status']='BLOCKED' if not report['cases'] else 'FAIL';report['error']=safe
        import traceback
        report['failure_frames']=[{'file':f.filename,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(exc.__traceback__)]
        if hasattr(exc,'errors'):report['validation_errors']=[{'loc':e['loc'],'type':e['type']} for e in exc.errors()]
        save()
        print(json.dumps({'status':report['status'],'safe_error':safe,'report':str(folder/'live.json')}));return 2
    finally:
        if provider:await provider.close()
        if index:await index.close()
if __name__=='__main__':sys.exit(asyncio.run(main()))
