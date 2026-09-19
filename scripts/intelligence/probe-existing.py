"""Focused real-service probes on a retained, owned B verification run.

The earlier run already authenticated these sessions. Reload the live server-side
principal from its own isolated schema for internal service probes; never emit tokens.
"""
import argparse,asyncio,json,os,secrets
from pathlib import Path
from datetime import datetime,timezone,timedelta
from dotenv import dotenv_values
from app.contracts.models import *
from app.contracts.errors import DomainError
from app.evidence.postgres import Postgres
from app.evidence.service import EvidencePlatform
from app.evidence.jobs import run_once
from app.intelligence.service import Intelligence
from app.intelligence.providers import ModelProvider,ProviderSettings
from app.intelligence.qdrant import QdrantIndex

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);parser.add_argument('--case',default='B-LONG');parser.add_argument('--followup',action='store_true');parser.add_argument('--semantic-only',action='store_true');parser.add_argument('--bundle',action='store_true');parser.add_argument('--topics',action='store_true');parser.add_argument('--artifact-negative',action='store_true');args=parser.parse_args()
    import re
    if not re.fullmatch('[a-z][a-z0-9_]{0,35}',args.run_id):raise SystemExit('Invalid run ID')
    folder=Path('scripts/intelligence/runs')/args.run_id;original=json.loads((folder/'live.json').read_text());case=next(c for c in original['cases'] if c['id']==args.case);pid=case['project_id'];cfg={**dotenv_values('.env'),**os.environ}
    db=Postgres(cfg.get('RELEX_LIVE_DATABASE_URL') or cfg.get('RELEX_DATABASE_URL') or '',original['schema']);p=EvidencePlatform(db,(folder/'secret').read_text(),request_deadline_seconds=240)
    async with db.connection() as connection:
        state=(await (await connection.execute('SELECT data FROM projects WHERE id=%s',(pid,))).fetchone())['data']
        uid=next(uid for uid,m in state['members'].items() if m['role']=='admin')
        session=await (await connection.execute('SELECT id,user_id,expires_at FROM sessions WHERE user_id=%s AND NOT revoked AND expires_at>now() ORDER BY expires_at DESC LIMIT 1',(uid,))).fetchone()
    principal=SessionPrincipal(user_id=session['user_id'],session_id=session['id'],expires_at=session['expires_at']);ctx=await p.authorize(principal,pid)
    provider=ModelProvider(ProviderSettings(base_url=cfg.get('RELEX_MODEL_BASE_URL') or '',model=cfg.get('RELEX_MODEL_NAME') or '',api_key=cfg.get('RELEX_MODEL_API_KEY') or cfg.get('OPENAI_API_KEY') or '',embedding_base_url=cfg.get('RELEX_EMBEDDING_BASE_URL') or '',embedding_model=cfg.get('RELEX_EMBEDDING_MODEL') or '',embedding_api_key=cfg.get('RELEX_EMBEDDING_API_KEY') or cfg.get('OPENAI_API_KEY') or ''))
    index=QdrantIndex(cfg.get('RELEX_QDRANT_URL') or 'http://127.0.0.1:16333',original['collection'],cfg.get('RELEX_QDRANT_API_KEY') or '')
    limits=RuntimeLimits(answer_search_rounds=3,repair_search_rounds=1,reviewer_passes=3,reviewer_search_rounds=3,tool_calls_per_phase=50,pages_per_phase=40,source_tokens_per_phase=120000,request_deadline_seconds=300)
    service=Intelligence(p.reader,p.retrieval,p.artifacts,p.ledger,provider,index,limits,(folder/'secret').read_bytes())
    result={'run_id':args.run_id,'project_id':pid,'started_at':datetime.now(timezone.utc).isoformat(),'substitutes':[]}
    try:
        if args.followup:
            conversation_id=case['answer']['conversation_id'];previous=case['answer']['id']
            job=await p.submit_upload(ctx,UploadInput(filename='explicit-correction.txt',record_type='report',content=b'Date: 2026-09-19\nExplicit correction: the report that PERSON_A and PERSON_B agreed October was incorrect. That agreement never happened. The November proposal remains unaccepted.'))
            for _ in range(20):
                await run_once(p,service,'b-followup');ctx=await p.authorize(principal,pid);status=await p.get_job(ctx,job.id)
                if status.state in ['completed','failed']:break
            assert status.state=='completed',status.error_code
            try:await p.get_answer(ctx,previous);raise AssertionError('Old answer remained eligible')
            except DomainError as exc:assert exc.code=='answer_unavailable'
            turn=await p.begin_chat(ctx,ChatInput(question='So was October actually agreed, and is November accepted?',conversation_id=conversation_id,request_id=secrets.token_hex(16)))
            candidate=await service.answer(ctx,turn.input);answer=await p.release_answer(ctx,turn.attempt,candidate)
            result.update(old_answer_invalidated=True,normalized_history=[h.model_dump(mode='json') for h in turn.input.history],answer=answer.model_dump(mode='json'))
        elif args.artifact_negative:
            class InvalidSpan:
                def __init__(self,real):self.real=real;self.injected=False
                def __getattr__(self,name):return getattr(self.real,name)
                async def stage_artifacts(self,cap,key,batch):
                    if batch.chunks and not self.injected:
                        self.injected=True;batch=batch.model_copy(deep=True)
                        batch.chunks[0].slices[0].span_id='deliberately-invalid-synthetic-span'
                    return await self.real.stage_artifacts(cap,key,batch)
            faulty=InvalidSpan(p.artifacts);service.artifacts=faulty
            job=await p.submit_upload(ctx,UploadInput(filename='invalid-artifact-probe.txt',record_type='report',content=b'Date: 2026-09-19\nThe equipment inspection is proposed. Approval is not recorded.'))
            for _ in range(30):
                await run_once(p,service,'b-invalid-span');ctx=await p.authorize(principal,pid);status=await p.get_job(ctx,job.id)
                if status.state in ['completed','failed']:break
            assert faulty.injected and status.state=='failed' and status.error_code=='contract_violation'
            result['real_generated_artifact_invalid_span_rejected']=status.model_dump(mode='json')
            class UnsupportedOverview:
                def __init__(self,real):self.real=real;self.injected=False
                def __getattr__(self,name):return getattr(self.real,name)
                async def stage_artifacts(self,cap,key,batch):
                    if any(memory.kind=='overview' for memory in batch.memories):
                        self.injected=True;batch=batch.model_copy(deep=True)
                        for memory in batch.memories:
                            if memory.kind=='overview':memory.text+=' PERSON_Z approved a budget of 7000000 euros and owns the launch.'
                    return await self.real.stage_artifacts(cap,key,batch)
            fault=UnsupportedOverview(p.artifacts);service.artifacts=fault
            job=await p.submit_upload(ctx,UploadInput(filename='overview-source-probe.txt',record_type='report',content=b'Date: 2026-09-19\nThe equipment inspection is proposed. Approval is not recorded.'))
            for _ in range(40):
                if not await run_once(p,service,'b-overview-negative'):break
            ctx=await p.authorize(principal,pid);overview=await p.get_overview(ctx)
            assert fault.injected
            assert all('7000000' not in claim.text and 'PERSON_Z' not in claim.text for claim in overview.claims)
            if overview.state!='ready':assert not overview.claims and not overview.receipts
            result['unsupported_overview_clause_withheld']=overview.model_dump(mode='json')
            result['fault_injection']='Mutated only an actual real-model artifact before real A staging; no fake repository/model/index responses. Actual final draft/reviewer and release remained active.'
        elif args.semantic_only:
            query='Has authorization crystallized?'
            lexical=await p.retrieval.lexical_candidates(ctx,query,SearchFilters(),100)
            assert not lexical
            found=await service.search_memory(ctx,SearchInput(query=query,filters=SearchFilters(),page=PageRequest(limit=100)))
            assert case['search']['items'][0]['record']['record_id'] in [hit.record.record_id for hit in found.items]
            result['semantic_only_record_ids']=[hit.record.record_id for hit in found.items]
            result['lexical_candidate_count']=len(lexical)
        elif args.bundle:
            content=b'From: PERSON_synthetic\nDate: 2026-09-01\nSubject: BUNDLE_FIRST_SENTINEL\nOctober is a proposal, not an agreement.\n-----\nFrom: PERSON_synthetic\nDate: 2026-09-02\nSubject: BUNDLE_SECOND_SENTINEL\nThe warehouse badge was approved.'
            job=await p.submit_upload(ctx,UploadInput(filename='two-record-bundle.txt',record_type='email',content=content))
            for _ in range(30):
                await run_once(p,service,'b-bundle');ctx=await p.authorize(principal,pid);status=await p.get_job(ctx,job.id)
                if status.state in ['completed','failed']:break
            assert status.state=='completed',status.error_code
            documents=await p.list_documents(ctx,PageRequest(limit=100));document=next(d for d in documents.items if d.latest_job_id==job.id)
            records=await p.list_records(ctx,document.id,PageRequest(limit=100));assert len(records.items)==2
            from app.intelligence.tools import ToolSession
            for record in records.items:
                session=ToolSession(service,ctx,limits,datetime.now(timezone.utc)+timedelta(seconds=180),3,progressive=False);cursor=None
                while True:
                    page=await session.call('read_record',{'record_id':record.record_id,'cursor':cursor});cursor=page.record_page.next_cursor
                    if cursor is None:break
                texts='\n'.join(span.text for spans in session.spans.values() for span in spans.values())
                assert not ('BUNDLE_FIRST_SENTINEL' in texts and 'BUNDLE_SECOND_SENTINEL' in texts)
                assert len(session.records)==1 and session.coverage().records[0].complete
            result['selected_bundle_records_only']=[r.record_id for r in records.items]
        elif args.topics:
            before={mid:m['data'] for mid,m in state['memories'].items() if m['valid'] and m['data']['kind']=='topic'}
            assert before
            job=await p.submit_upload(ctx,UploadInput(filename='unrelated-badge.txt',record_type='report',content=b'Date: 2026-09-19\nThe unrelated warehouse security badge COLOR-92 was approved.'))
            for _ in range(30):
                if not await run_once(p,service,'b-unrelated'):break
            ctx=await p.authorize(principal,pid)
            same=[]
            for mid,old in before.items():
                current=await p.reader.read_memory(ctx,mid)
                assert current.model_dump(mode='json')==old
                same.append(mid)
            result['unchanged_topic_artifacts']=same;result['overview']=(await p.get_overview(ctx)).model_dump(mode='json')
            assert result['overview']['state']=='ready'
        else:
            rid=case['search']['items'][0]['record']['record_id']
            found=await index._call('POST',index.path+'/points/scroll',{'filter':{'must':[{'key':'project_id','match':{'value':pid}}]},'limit':100,'with_payload':True,'with_vector':True})
            points=found['points'];entries=[IndexEntry(**row['payload']) for row in points];vectors=[row['vector'] for row in points]
            assert await index.delete([e.id for e in entries])
            try:
                lexical=await service.search_memory(ctx,SearchInput(query='ZXQ-771',filters=SearchFilters(),page=PageRequest()))
                assert rid in [h.record.record_id for h in lexical.items]
                result['lexical_only_preserved']=[h.record.record_id for h in lexical.items]
            finally:assert await index.upsert(entries,vectors)
            query='Is the proposed rollout permitted to proceed without capacity authorization?'
            vector=(await provider.embed([query]))[0];semantic=await index.search(vector,pid,100)
            assert semantic;result['semantic_paraphrase_entry_ids']=[r['id'] for r in semantic]
            wrong=entries[0].model_copy(update={'id':'22222222-2222-5222-8222-222222222222','project_id':'other-owned-synthetic-project'})
            await index.upsert([wrong],[vectors[0]])
            try:
                hits=await index.search(vector,pid,100);assert wrong.id not in [r['id'] for r in hits]
                check=await p.validate_candidates(ctx,[CandidateRef(entry_id=wrong.id,record_id=wrong.record_id,record_version=wrong.record_version,chunk_id=wrong.chunk_id,input_hash=wrong.input_hash,rank=1)],SearchFilters())
                assert not check.eligible and check.rejected_entry_ids==[wrong.id];result['wrong_project_candidate_rejected']=True
            finally:assert await index.delete([wrong.id])
            page=await p.reader.read_record(ctx,rid,PageRequest(limit=1));cursor=page.record_page.next_cursor;assert cursor
            job=await p.submit_upload(ctx,UploadInput(filename='unrelated-source.txt',record_type='report',content=b'Date: 2026-09-02\nWarehouse badge ZXQ-OTHER was discussed.'))
            for _ in range(20):
                await run_once(p,service,'b-cursor');ctx=await p.authorize(principal,pid);status=await p.get_job(ctx,job.id)
                if status.state in ['completed','failed']:break
            assert status.state=='completed',status.error_code
            try:await p.reader.read_record(ctx,rid,PageRequest(cursor=cursor,limit=1));raise AssertionError('Old cursor accepted')
            except DomainError as exc:assert exc.code=='stale_cursor';result['stale_cursor_rejected']=True
            assert await index.verify(entries);result['unrelated_record_vectors_unchanged']=[e.id for e in entries]
        result['provider_events']=provider.events;result['safe_traces']=service.traces;result['status']='EXECUTED'
    except Exception as exc:
        result['status']='FAIL';result['safe_error']=exc.code if isinstance(exc,DomainError) else type(exc).__name__
        raise
    finally:
        (folder/('followup.json' if args.followup else 'artifact-negative.json' if args.artifact_negative else 'semantic-only.json' if args.semantic_only else 'bundle.json' if args.bundle else 'topics.json' if args.topics else 'retrieval-extra.json')).write_text(json.dumps(result,indent=2));await provider.close();await index.close()
    print(json.dumps({'status':result['status'],'report':str(folder/('followup.json' if args.followup else 'artifact-negative.json' if args.artifact_negative else 'semantic-only.json' if args.semantic_only else 'bundle.json' if args.bundle else 'topics.json' if args.topics else 'retrieval-extra.json'))}))
asyncio.run(main())
