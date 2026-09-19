"""Read-only tools bound to a server context and one finite phase budget."""
from __future__ import annotations
import math
import asyncio
from datetime import datetime,timezone
from app.contracts.models import *
from app.contracts.errors import DomainError
from .retrieval import snapshot

class BudgetExhausted(Exception):pass

class ToolSession:
    def __init__(self,owner,ctx,limits,deadline,rounds):
        self.owner,self.ctx,self.limits,self.deadline=owner,ctx,limits,deadline
        self.round_limit=rounds
        self.calls=self.pages=self.tokens=self.searches=0
        self.records={};self.spans={};self.dependencies={};self.results=[];self.trace=[]
        self.exhausted=False;self.pending_searches=set();self.pending_histories=set()

    def check(self):
        if datetime.now(timezone.utc)>=self.deadline:raise DomainError("provider_unavailable")
        if self.calls>=self.limits.tool_calls_per_phase:
            self.exhausted=True;raise BudgetExhausted()

    def account(self,value,page=False):
        # Conservative Unicode-codepoint bound; never counts a large source as zero tokens.
        text=value.model_dump_json() if hasattr(value,"model_dump_json") else str(value)
        charge=len(text)
        if self.tokens+charge>self.limits.source_tokens_per_phase or (page and self.pages>=self.limits.pages_per_phase):
            self.exhausted=True;raise BudgetExhausted()
        self.tokens+=charge;self.pages+=int(page)

    async def call(self,name,args):
        self.check()
        try:
            async with asyncio.timeout((self.deadline-datetime.now(timezone.utc)).total_seconds()):
                return await self._call(name,args)
        except TimeoutError:raise DomainError("provider_unavailable") from None

    async def _call(self,name,args):
        self.check();self.calls+=1
        allowed={"search_memory":{"query","filters","cursor"},"read_record":{"record_id","cursor"},
          "read_memory":{"memory_id"},"get_decision_history":{"topic_id","scope","as_of","cursor"},
          "expand_context":{"record_id","span_id"}}
        if name not in allowed or not isinstance(args,dict) or set(args)-allowed[name]:raise DomainError("invalid_input")
        if name=="search_memory":
            if self.searches>=self.round_limit:self.exhausted=True;raise BudgetExhausted()
            self.searches+=1
            result=await self.owner.search_memory(self.ctx,SearchInput(query=args["query"],filters=SearchFilters(**args.get("filters",{})),page=PageRequest(cursor=args.get("cursor"),limit=25)))
            self.account(result,page=True)
            query_key=(args["query"],str(args.get("filters",{})))
            if result.next_cursor:self.pending_searches.add(query_key)
            else:self.pending_searches.discard(query_key)
            trace_ids=[x.record.record_id for x in result.items]
        elif name=="read_record":
            result=await self.owner.reader.read_record(self.ctx,args["record_id"],PageRequest(cursor=args.get("cursor"),limit=10))
            self.account(result,page=True)
            page=result.record_page
            if page.snapshot!=snapshot(self.ctx):raise DomainError("evidence_changed")
            key=(page.record.record_id,page.record.record_version)
            record=self.records.setdefault(key,{"summary":page.record,"chunks":[],"end":False,"start":False})
            record["start"]|=not args.get("cursor");record["end"]|=page.complete
            record["chunks"]=list(dict.fromkeys(record["chunks"]+page.returned_chunk_ids))
            self.spans.setdefault(key,{}).update({s.span_id:s for s in page.spans})
            self.dependencies.setdefault(key,set()).update(s.span_id for s in page.spans)
            trace_ids=page.returned_chunk_ids
        elif name=="read_memory":
            result=await self.owner.reader.read_memory(self.ctx,args["memory_id"]);self.account(result)
            for dep in result.dependencies:self.dependencies.setdefault((dep.record_id,dep.record_version),set()).update(dep.span_ids)
            trace_ids=[result.id]
        elif name=="get_decision_history":
            result=await self.owner.get_decision_history(self.ctx,HistoryQuery(topic_id=args["topic_id"],scope=args["scope"],as_of=args.get("as_of")),PageRequest(cursor=args.get("cursor")))
            self.account(result,page=True)
            history_key=(args["topic_id"],args["scope"])
            if result.next_cursor:self.pending_histories.add(history_key)
            else:self.pending_histories.discard(history_key)
            for event in result.items:
                for ref in event.evidence:self.dependencies.setdefault((ref.record_id,ref.record_version),set()).update(ref.span_ids)
            trace_ids=[e.id for e in result.items]
        else:
            matches=[(key,r) for key,r in self.records.items() if key[0]==args["record_id"]]
            if not matches:raise DomainError("invalid_input")
            key,record=matches[0]
            ref=EvidenceRef(project_id=self.ctx.project_id,original_doc_id=record["summary"].original_doc_id,
                record_id=key[0],record_version=key[1],span_ids=[args["span_id"]])
            result=await self.owner.reader.expand_context(self.ctx,ref)
            self.account(result,page=True)
            self.spans.setdefault(key,{}).update({s.span_id:s for s in result.spans})
            self.dependencies.setdefault(key,set()).update(s.span_id for s in result.spans)
            trace_ids=[s.span_id for s in result.spans]
        self.results.append({"tool":name,"result":result.model_dump(mode="json")})
        self.trace.append({"tool":name,"ids":trace_ids,"calls":self.calls,"pages":self.pages,"source_tokens_bound":self.tokens,"search_rounds":self.searches})
        return result

    async def discover(self,query):
        hits=await self.call("search_memory",{"query":query})
        for hit in hits.items:
            cursor=None
            while True:
                page=await self.call("read_record",{"record_id":hit.record.record_id,"cursor":cursor})
                cursor=page.record_page.next_cursor
                if cursor is None:break

    def coverage(self):
        records=[RecordCoverage(record_id=key[0],record_version=key[1],total_chunks=r["summary"].total_chunks,
            supplied_chunk_ids=r["chunks"],complete=r["start"] and r["end"] and len(r["chunks"])==r["summary"].total_chunks)
            for key,r in sorted(self.records.items())]
        incomplete=[r.record_id for r in records if not r.complete]
        limits=[]
        if incomplete:limits.append(Limitation(code="unread_chunks",record_ids=incomplete))
        if self.exhausted:limits.append(Limitation(code="budget_exhausted",record_ids=[]))
        if self.pending_searches or self.pending_histories:limits.append(Limitation(code="history_incomplete",record_ids=[]))
        if not records:limits.append(Limitation(code="no_evidence",record_ids=[]))
        return Coverage(state="insufficient" if not records else "partial" if limits else "complete",records=records,limitations=limits)

    def deps(self):
        return [Dependency(record_id=k[0],record_version=k[1],span_ids=sorted(v)) for k,v in sorted(self.dependencies.items())]
