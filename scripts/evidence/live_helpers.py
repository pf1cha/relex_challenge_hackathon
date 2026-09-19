"""Real adapters for owned live scenarios; never used by production composition."""
import os
from dotenv import dotenv_values
from app.evidence.postgres import Postgres
from app.evidence.service import EvidencePlatform
from app.contracts.models import RuntimeLimits
def build(schema,secret,lease_seconds=300):
    from app.intelligence.providers import ModelProvider,ProviderSettings
    from app.intelligence.qdrant import QdrantIndex
    from app.intelligence.service import Intelligence
    e={**{k:v for k,v in dotenv_values(".env").items() if v is not None},**os.environ}
    db=Postgres(e.get("RELEX_DATABASE_URL",""),schema)
    p=EvidencePlatform(db,secret,lease_seconds=lease_seconds)
    provider=ModelProvider(ProviderSettings(base_url=e.get("RELEX_MODEL_BASE_URL",""),model=e.get("RELEX_MODEL_NAME",""),api_key=e.get("RELEX_MODEL_API_KEY") or e.get("OPENAI_API_KEY",""),embedding_base_url=e.get("RELEX_EMBEDDING_BASE_URL",""),embedding_model=e.get("RELEX_EMBEDDING_MODEL",""),embedding_api_key=e.get("RELEX_EMBEDDING_API_KEY") or e.get("OPENAI_API_KEY",""),timeout_seconds=120))
    index=QdrantIndex(e.get("RELEX_QDRANT_URL") or "http://127.0.0.1:16333",schema,e.get("RELEX_QDRANT_API_KEY",""))
    limits=RuntimeLimits(answer_search_rounds=3,repair_search_rounds=1,reviewer_passes=2,reviewer_search_rounds=3,tool_calls_per_phase=24,pages_per_phase=24,source_tokens_per_phase=24000,request_deadline_seconds=120)
    b=Intelligence(p.reader,p.retrieval,p.artifacts,p.ledger,provider,index,limits,p.secret)
    return p,b,provider,index
