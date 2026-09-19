"""Only production composition root imports concrete evidence and intelligence."""
from dataclasses import dataclass
import os
from app.config import RuntimeSettings
from app.contracts.models import RuntimeLimits
from app.contracts.ports import Services

@dataclass
class Runtime:
    settings: RuntimeSettings
    services: Services
    evidence: object
    intelligence: object
    provider: object
    index: object
    async def readiness(self):
        result={"database":"unavailable","index":"unavailable","model":"configured_unverified"}
        try:
            if await self.evidence.db.ready(): result["database"]="ready"
        except Exception: pass
        try:
            response=await self.index.client.get(self.index.url+"/healthz")
            if response.is_success: result["index"]="ready"
        except Exception: pass
        if not self.settings.model_name or not self.settings.embedding_model:
            result["model"]="unconfigured"
        return result
    async def close(self):
        await self.provider.close()
        await self.index.close()
        await self.evidence.db.close()

def build_runtime(settings: RuntimeSettings | None = None) -> Runtime:
    from app.evidence.postgres import Postgres
    from app.evidence.service import EvidencePlatform
    from app.intelligence.providers import ModelProvider, ProviderSettings
    from app.intelligence.qdrant import QdrantIndex
    from app.intelligence.service import Intelligence
    settings=settings or RuntimeSettings.from_env()
    db=Postgres(settings.database_url,schema=os.environ.get("RELEX_DATABASE_SCHEMA","relex"))
    evidence=EvidencePlatform(db,settings.secret,upload_limit_bytes=settings.http.upload_limit_bytes,
        request_deadline_seconds=settings.http.request_timeout_seconds)
    provider=ModelProvider(ProviderSettings(base_url=settings.model_url,model=settings.model_name,
        api_key=settings.model_key,embedding_base_url=settings.embedding_url,
        embedding_model=settings.embedding_model,embedding_api_key=settings.embedding_key,
        timeout_seconds=min(120,settings.http.request_timeout_seconds)))
    index=QdrantIndex(settings.qdrant_url,settings.collection,settings.qdrant_key)
    limits=RuntimeLimits(answer_search_rounds=3,repair_search_rounds=1,reviewer_passes=2,
        reviewer_search_rounds=3,tool_calls_per_phase=int(os.environ.get("RELEX_TOOL_CALLS_PER_PHASE","24")),
        pages_per_phase=int(os.environ.get("RELEX_PAGES_PER_PHASE","24")),
        source_tokens_per_phase=int(os.environ.get("RELEX_SOURCE_TOKENS_PER_PHASE","24000")),
        request_deadline_seconds=settings.http.request_timeout_seconds)
    intelligence=Intelligence(evidence.reader,evidence.retrieval,evidence.artifacts,evidence.ledger,
        provider,index,limits,settings.secret.encode())
    services=Services(evidence.auth,evidence.projects,evidence.documents,evidence.sources,
        evidence.administration,evidence.conversations,intelligence)
    return Runtime(settings,services,evidence,intelligence,provider,index)
