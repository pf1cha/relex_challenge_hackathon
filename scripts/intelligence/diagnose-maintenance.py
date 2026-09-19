"""Read-only real-provider schema probe of the retained synthetic failed source."""
import asyncio,json,os
from pathlib import Path
from datetime import datetime,timezone
from dotenv import dotenv_values
from app.evidence.postgres import Postgres
from app.contracts.models import *
from app.intelligence.providers import ModelProvider,ProviderSettings
from app.intelligence.service import Intelligence
from app.intelligence.maintenance import supported_time

async def main():
    cfg={**dotenv_values('.env'),**os.environ};c=json.loads(Path('.runtime/c_c_late2/private.json').read_text())
    db=Postgres('postgresql://relex_dev@127.0.0.1:15432/postgres',c['schema'])
    async with db.connection() as connection:
        state=(await(await connection.execute('SELECT data FROM projects WHERE id=%s',(c['project_id'],))).fetchone())['data']
    raw=state['records']['08b27e0d-89ae-4c85-818f-ca173c12a58f'];record=StagedRecord(**{key:raw[key] for key in StagedRecord.model_fields})
    provider=ModelProvider(ProviderSettings(base_url=cfg.get('RELEX_MODEL_BASE_URL') or '',model=cfg.get('RELEX_MODEL_NAME') or '',api_key=cfg.get('RELEX_MODEL_API_KEY') or cfg.get('OPENAI_API_KEY') or '',embedding_base_url=cfg.get('RELEX_EMBEDDING_BASE_URL') or '',embedding_model=cfg.get('RELEX_EMBEDDING_MODEL') or '',embedding_api_key=cfg.get('RELEX_EMBEDDING_API_KEY') or cfg.get('OPENAI_API_KEY') or ''))
    limits=RuntimeLimits(answer_search_rounds=3,repair_search_rounds=1,reviewer_passes=3,reviewer_search_rounds=3,tool_calls_per_phase=50,pages_per_phase=40,source_tokens_per_phase=120000,request_deadline_seconds=300)
    service=Intelligence(None,None,None,None,provider,None,limits,b'private-synthetic-probe-key-000000')
    results=[]
    try:
        for attempt in range(3):
            try:
                value=await service._maintenance_generation(record)
                known={span.span_id for span in record.spans}
                diagnostics=[]
                for event in value.get('events',[]):
                    diagnostics.append({'keys':sorted(event),'kind':event.get('kind'),'span_count':len(event.get('span_ids',[])),
                        'unknown_span_count':sum(1 for i in event.get('span_ids',[]) if i not in known),'prior_count':len(event.get('prior_event_ids',[])),
                        'types':{key:type(v).__name__ for key,v in event.items()}})
                results.append({'attempt':attempt+1,'status':'generated','event_schema':diagnostics})
            except Exception as exc:results.append({'attempt':attempt+1,'status':'failure','code':getattr(exc,'code',type(exc).__name__),'diagnostic':getattr(exc,'diagnostic',{})})
        directory=Path('scripts/intelligence/runs/b_diag_late2');directory.mkdir(exist_ok=True)
        output={'source_schema':c['schema'],'source_version':record.record_version,'probe_started_at':datetime.now(timezone.utc).isoformat(),'results':results,'provider_events':provider.events}
        (directory/'schema-probe.json').write_text(json.dumps(output,indent=2));print(json.dumps(output))
    finally:await provider.close()
asyncio.run(main())
