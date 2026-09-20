from app.contracts.models import RuntimeLimits
from .answering import Answers
from .maintenance import Maintenance
from .retrieval import Retrieval

class Intelligence(Answers,Maintenance):
    def __init__(self,reader,retrieval,artifacts,ledger,provider,index,limits: RuntimeLimits,cursor_secret: bytes):
        self.reader,self.retrieval,self.artifacts,self.ledger=reader,retrieval,artifacts,ledger
        self.provider,self.index,self.limits=provider,index,limits
        if not (1<=limits.answer_search_rounds<=20 and 0<=limits.repair_search_rounds<=1 and 1<=limits.reviewer_passes<=3 and 1<=limits.reviewer_search_rounds<=3):
            raise ValueError("Invalid phase limits")
        if min(limits.tool_calls_per_phase,limits.pages_per_phase,limits.source_tokens_per_phase,limits.request_deadline_seconds)<1:raise ValueError("Finite positive limits required")
        self.search=Retrieval(reader,retrieval,provider,index,cursor_secret)
        self.traces=[]

    async def search_memory(self,ctx,input):return await self.search.search(ctx,input)
    async def search_agent_memory(self,ctx,input):return await self.search.search(ctx,input,include_source=False)
    async def search_sources(self,ctx,input):return await self.search.search(ctx,input,include_source=True)
    async def get_decision_history(self,ctx,query,page):return await self.retrieval.read_history(ctx,query,page)
