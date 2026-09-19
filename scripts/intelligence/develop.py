"""Independent development runner. Reports substituted boundaries explicitly."""
import argparse,asyncio,json,re
from pathlib import Path
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from dotenv import dotenv_values
from app.contracts.models import *
from app.intelligence.service import Intelligence
from app.intelligence.providers import ModelProvider,ProviderSettings
from app.intelligence.qdrant import QdrantIndex
from tests.intelligence.fixture_ports import CanonicalFixture

class ScriptedProvider:
    settings=SimpleNamespace(model='development-script')
    embedding_model='development-vector'
    events=[]
    async def embed(self,texts,**kwargs):return [[1.0,0.0,0.0] for _ in texts]
    async def generate(self,role,system,payload,**kwargs):
        if role=='maintenance':
            r=payload['record'];return {'description':'Synthetic record','summary':'\n'.join(s['text'] for s in r['spans']),'span_ids':[s['span_id'] for s in r['spans']],'topics':[],'events':[]}
        if role=='review':
            return {'retrieval':{'verdict':'sufficient','missing_context':[],'suggested_queries':[],'suggested_record_ids':[]},
                'results':[{'claim_id':c['id'],'verdict':'pass','reason_code':'supported','receipt_ids':c['receipt_ids'],'repair_request':None} for c in payload['candidate']['claims']]}
        source_searches=[r['result'] for r in payload['tool_results'] if r['tool']=='search_sources']
        sources=[r['result']['record_page'] for r in payload['tool_results'] if r['tool']=='read_record']
        if not source_searches:
            return {'tools':[{'name':'search_sources','arguments':{'query':payload['question']}}]}
        if not sources:
            hits=source_searches[0]['items']
            if not hits:return {'claims':[],'cannot_establish':'no_evidence'}
            return {'tools':[{'name':'read_record','arguments':{'record_id':hits[0]['record']['record_id']}}]}
        r=sources[0];span=r['spans'][0]
        return {'claims':[{'text':span['text'],'status':None,'scope':None,'effective_at':None,'evidence':[{'record_id':r['record']['record_id'],'record_version':r['record']['record_version'],'span_ids':[span['span_id']]}]}],'cannot_establish':None}
    async def close(self):pass
class MemoryIndex:
    def __init__(self):self.entries={}
    async def ensure(self,d):pass
    async def upsert(self,entries,vectors):self.entries.update({e.id:e.model_dump(mode='json') for e in entries});return True
    async def verify(self,entries):return all(self.entries.get(e.id)==e.model_dump(mode='json') for e in entries)
    async def search(self,v,p,limit):return [{'id':i,'payload':e} for i,e in self.entries.items() if e['project_id']==p][:limit]
    async def close(self):pass

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);parser.add_argument('--mode',choices=['deterministic','live'],default='deterministic');parser.add_argument('--case',default='B-C1');args=parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]{1,60}',args.run_id):raise SystemExit('Invalid run ID')
    cfg=dotenv_values('.env');repo=CanonicalFixture('b-dev-'+args.run_id)
    if args.mode=='live':
        provider=ModelProvider(ProviderSettings(base_url=cfg.get('RELEX_MODEL_BASE_URL') or '',model=cfg.get('RELEX_MODEL_NAME') or '',api_key=cfg.get('RELEX_MODEL_API_KEY') or cfg.get('OPENAI_API_KEY') or '',embedding_base_url=cfg.get('RELEX_EMBEDDING_BASE_URL') or '',embedding_model=cfg.get('RELEX_EMBEDDING_MODEL') or '',embedding_api_key=cfg.get('RELEX_EMBEDDING_API_KEY') or cfg.get('OPENAI_API_KEY') or ''))
        index=QdrantIndex(cfg.get('RELEX_QDRANT_URL') or 'http://127.0.0.1:16333','b_dev_'+args.run_id,cfg.get('RELEX_QDRANT_API_KEY') or '')
    else:provider,index=ScriptedProvider(),MemoryIndex()
    limits=RuntimeLimits(answer_search_rounds=3,repair_search_rounds=1,reviewer_passes=3,reviewer_search_rounds=3,tool_calls_per_phase=40,pages_per_phase=30,source_tokens_per_phase=100000,request_deadline_seconds=240)
    service=Intelligence(repo,repo,repo,repo,provider,index,limits,b'development-only-signing-key-00000')
    ctx=RequestContext(user_id='synthetic',session_id='synthetic',project_id=repo.project_id,role='admin',access_revision=1,corpus_generation=1,privacy_generation=0)
    case=next(c for c in json.loads(Path('backend/tests/intelligence/cases.json').read_text()) if c['id']==args.case)
    results=[]
    try:
        for n,text in enumerate(case['records']):
            ref=repo.add(text,n);cap=JobCapability(capability_id='cap-'+str(n),job_id='job-'+str(n),project_id=repo.project_id,lease_token='development',lifecycle_revision=1,allowed_stage='extracted',allowed_record_versions=[ref],publication_generation=1,expires_at=datetime.now(timezone.utc)+timedelta(minutes=10))
            first=await service.process_record(cap,ref);second=await service.process_record(cap,ref)
            assert first.batch_id==second.batch_id and second.unchanged_entry_ids==first.changed_entry_ids
            results.append(first.model_dump(mode='json'))
        candidate=await service.answer(ctx,AnswerInput(question=NormalizedText(text=case['question'],person_ids=[],ambiguous=False),history=[],request_id='request',conversation_id='conversation',deadline=datetime.now(timezone.utc)+timedelta(seconds=240)))
        out={'status':'DEVELOPMENT_ONLY','substitutes':['canonical repository','eligibility','staging','ledger']+(['model','index'] if args.mode=='deterministic' else []),'run_id':args.run_id,'case':case,'maintenance':results,'candidate':candidate.model_dump(mode='json'),'provider_events':provider.events,'traces':service.traces}
        folder=Path('scripts/intelligence/runs')/args.run_id;folder.mkdir(parents=True,exist_ok=True);(folder/'development.json').write_text(json.dumps(out,indent=2))
        print(json.dumps({'status':'DEVELOPMENT_ONLY','claims':[c.text for c in candidate.claims],'cannot_establish':candidate.cannot_establish,'report':str(folder/'development.json')}))
    finally:await provider.close();await index.close()
asyncio.run(main())
