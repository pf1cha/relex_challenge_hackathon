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
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);parser.add_argument('--case',action='append');parser.add_argument('--negative',action='store_true');parser.add_argument('--retrieval',action='store_true');parser.add_argument('--stale',action='store_true');args=parser.parse_args()
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
        if args.retrieval:
            cases=[{'id':'B-LONG','records':['Date: 2026-09-01\nZXQ-771 is a proposed launch.\n'+('Capacity evaluation remains open. Operational logistics are under discussion. '*24+'\n')*12+'The final qualification is that capacity approval is absent, and the launch is not accepted.'], 'question':'Is ZXQ-771 an accepted launch?', 'expected':['proposal','late qualification','not accepted'],'prohibited':['accepted launch']}]
        for case in cases:
            if args.case and case['id'] not in args.case:continue
            observed={'id':case['id'],'status':'RUNNING','expected':case['expected'],'prohibited':case['prohibited']};report['cases'].append(observed);save()
            password=secrets.token_urlsafe(24);email=case['id'].lower()+'@'+args.run_id+'.invalid'
            uid=await platform.bootstrap_user(email,password,'Synthetic Member')
            pid=await platform.bootstrap_project('Synthetic '+case['id'],uid)
            login=await platform.login(email,password);principal=await platform.authenticate(login.session_token)
            observed['project_id']=pid;observed['jobs']=[]
            if args.retrieval:
                ctx=await platform.authorize(principal,pid)
                person=await platform.associate_person(ctx,PersonInput(display_name='Synthetic Operator',kind='employee',contacts=[]))
                case['records'][0]=case['records'][0].replace('ZXQ-771 is a proposed launch.','Synthetic Operator proposed ZXQ-771 as a launch.')
                observed['person_id']=person.id
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
            observed['overview']= (await platform.get_overview(ctx)).model_dump(mode='json')
            observed['jobs_after_drain']=[j.model_dump(mode='json') for j in (await platform.list_jobs(ctx,PageRequest(limit=100))).items]
            documents=await platform.list_documents(ctx,PageRequest(limit=100));observed['documents']=[d.model_dump(mode='json') for d in documents.items]
            search=await service.search_memory(ctx,SearchInput(query=case['question'],filters=SearchFilters(),page=PageRequest(limit=100)))
            observed['search']=search.model_dump(mode='json')
            if args.retrieval:
                record=search.items[0].record
                filters=[SearchFilters(record_type='report'),SearchFilters(original_doc_id=record.original_doc_id),SearchFilters(date_from='2026-09-01'),SearchFilters(date_to='2026-09-01'),SearchFilters(record_type='report',original_doc_id=record.original_doc_id,date_from='2026-09-01',date_to='2026-09-01')]
                payloads=(await index.scan(pid))['points']
                topics=list(dict.fromkeys(t for point in payloads for t in point['payload']['topic_ids']))
                filters.append(SearchFilters(person_id=person.id))
                if topics:filters.append(SearchFilters(topic_id=topics[0]))
                filters.append(SearchFilters(record_type='report',original_doc_id=record.original_doc_id,date_from='2026-09-01',date_to='2026-09-01',person_id=person.id,topic_id=topics[0] if topics else None))
                outcomes=[]
                for filt in filters:
                    found=await service.search_memory(ctx,SearchInput(query='ZXQ-771',filters=filt,page=PageRequest(limit=100)))
                    assert record.record_id in [h.record.record_id for h in found.items]
                    outcomes.append({'filters':filt.model_dump(mode='json'),'record_ids':[h.record.record_id for h in found.items]})
                excluded=await service.search_memory(ctx,SearchInput(query='ZXQ-771',filters=SearchFilters(record_type='email'),page=PageRequest()))
                assert not excluded.items
                lexical=await platform.retrieval.lexical_candidates(ctx,'ZXQ-771',SearchFilters(),100)
                assert lexical
                cursor=None;pages=[];seen=[];spans=[]
                while True:
                    page=await platform.reader.read_record(ctx,record.record_id,PageRequest(cursor=cursor,limit=1))
                    pages.append(page.model_dump(mode='json'));seen+=page.record_page.returned_chunk_ids;spans += [s.text for s in page.record_page.spans]
                    cursor=page.record_page.next_cursor
                    if cursor is None:break
                assert len(pages)>1 and len(set(seen))==record.total_chunks and any('final qualification' in text for text in spans)
                observed['filter_observations']=outcomes;observed['negative_type_filter_empty']=True;observed['lexical_entry_ids']=[c.entry_id for c in lexical];observed['ordered_pages']=pages
                # Inject a stale candidate payload into our real Qdrant collection; canonical validation must omit it.
                from app.contracts.hashing import make_entry_id
                first_point=next(iter((await index.scan(pid))['points']))
                stale=IndexEntry(**first_point['payload']).model_copy(update={'record_version':999,'id':'11111111-1111-5111-8111-111111111111'})
                vec=(await provider.embed(['ZXQ-771 is accepted']))[0]
                await index.upsert([stale],[vec])
                rejected=await platform.retrieval.validate_candidates(ctx,[CandidateRef(entry_id=stale.id,record_id=stale.record_id,record_version=999,chunk_id=stale.chunk_id,input_hash=stale.input_hash,rank=1)],SearchFilters())
                assert rejected.rejected_entry_ids==[stale.id] and not rejected.eligible
                scoped=await service.search_memory(ctx,SearchInput(query='ZXQ-771',filters=SearchFilters(),page=PageRequest()))
                assert all(h.record.record_version!=999 for h in scoped.items)
                assert await index.delete([stale.id]);observed['stale_index_candidate_rejected']=True
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
            if args.stale:
                from datetime import timedelta
                original=None
                for hit in search.items:
                    page=await platform.reader.read_record(ctx,hit.record.record_id,PageRequest(limit=100))
                    if any('report:' in span.text.lower() for span in page.record_page.spans):original=page.record_page;break
                assert original is not None
                ref=EvidenceRef(project_id=pid,original_doc_id=original.record.original_doc_id,record_id=original.record.record_id,record_version=original.record.record_version,span_ids=[s.span_id for s in original.spans])
                receipt=await platform.reader.make_receipt(ctx,ref)
                stale_payload=ReviewedPayload(claims=[Claim(id='deliberately-stale',text='October is the current agreed launch.',receipt_ids=[receipt.id],status='commitment',scope=None,effective_at=None)],receipts=[receipt],dependencies=[Dependency(record_id=ref.record_id,record_version=ref.record_version,span_ids=ref.span_ids)],coverage=Coverage(state='complete',records=[RecordCoverage(record_id=ref.record_id,record_version=ref.record_version,total_chunks=original.total_chunks,supplied_chunk_ids=original.returned_chunk_ids,complete=True)],limitations=[]),cannot_establish=None,snapshot=candidate.snapshot)
                corrected,verdicts=await service._review(ctx,'What is the current agreed launch?',stale_payload,datetime.now(timezone.utc)+timedelta(seconds=180))
                assert verdicts[0].verdict=='fail'
                assert any(d.record_id!=ref.record_id for d in corrected.dependencies)
                observed['stale_draft_independent_counterevidence']={'verdicts':[v.model_dump(mode='json') for v in verdicts],'dependency_record_ids':[d.record_id for d in corrected.dependencies]}
            if args.negative and candidate.claims:
                from datetime import timedelta
                from dataclasses import replace
                payload=ReviewedPayload(**{k:candidate.model_dump()[k] for k in ['claims','receipts','dependencies','coverage','cannot_establish','snapshot']})
                payload.claims[0].text='PERSON_Z approved a budget of 7000000 euros and is the launch owner.'
                reviewed,verdicts=await service._review(ctx,case['question'],payload,datetime.now(timezone.utc)+timedelta(seconds=180))
                assert next(r for r in verdicts if r.claim_id==payload.claims[0].id).verdict=='fail'
                observed['unsupported_attribution_rejected']=[r.model_dump(mode='json') for r in verdicts]
                broken=ModelProvider(replace(provider.settings,base_url='http://127.0.0.1:1/v1',embedding_base_url='http://127.0.0.1:1/v1',timeout_seconds=2))
                broken_service=Intelligence(platform.reader,platform.retrieval,platform.artifacts,platform.ledger,broken,index,limits,secret_file.read_bytes())
                try:
                    await broken_service.answer(ctx,begin.input)
                    raise AssertionError('Unavailable provider returned an answer')
                except DomainError as exc:
                    assert exc.code=='provider_unavailable';observed['unavailable_provider_rejected']=True
                finally:await broken.close()
                tiny=limits.model_copy(update={'tool_calls_per_phase':1,'pages_per_phase':1,'source_tokens_per_phase':1})
                limited=Intelligence(platform.reader,platform.retrieval,platform.artifacts,platform.ledger,provider,index,tiny,secret_file.read_bytes())
                bounded=await limited.answer(ctx,begin.input)
                assert not bounded.claims;observed['budget_exhaustion_withheld']=bounded.model_dump(mode='json')
                altered=candidate.model_copy(deep=True);altered.receipts[0].quote+=' altered'
                attempt=await platform.begin_chat(ctx,chat.model_copy(update={'request_id':secrets.token_hex(16)}))
                try:
                    await platform.release_answer(ctx,attempt.attempt,altered)
                    raise AssertionError('Altered quote was released')
                except DomainError as exc:
                    assert exc.code=='contract_violation';observed['altered_quote_rejected']=True
                    await platform.fail_chat(ctx,attempt.attempt,exc.code)
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
