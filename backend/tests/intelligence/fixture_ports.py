"""Development-only canonical substitutes. Never imported by production or live verifier."""
from datetime import datetime,timezone
from uuid import uuid4
from app.contracts.models import *
from app.contracts.errors import DomainError
from app.intelligence.chunking import stable_id

class CanonicalFixture:
    def __init__(self,project_id):
        self.project_id=project_id;self.records={};self.batches={};self.ops={};self.entries={};self.events=[]
    def add(self,text,n):
        rid=stable_id(self.project_id,'record',n)
        spans=[Span(span_id=stable_id(rid,i),ordinal=i,text=line,source_location=SourceLocation(line_start=i+1,line_end=i+1,paragraph=None,message_ordinal=None,turn_ordinal=None,timestamp_label=None)) for i,line in enumerate(text.splitlines())]
        self.records[rid]=StagedRecord(project_id=self.project_id,original_doc_id=stable_id(self.project_id,'doc',n),record_id=rid,record_version=1,record_type='report',title='Synthetic evidence '+str(n),source_time=SourceTime(value='2026-09-01',precision='day',timezone=None),spans=spans,person_ids=[],duplicate_of=None)
        return RecordVersionRef(record_id=rid,record_version=1)
    def summary(self,r):
        return RecordSummary(record_id=r.record_id,original_doc_id=r.original_doc_id,record_version=r.record_version,title=r.title,record_type=r.record_type,source_time=r.source_time,total_chunks=len([e for e in self.entries.values() if e.record_id==r.record_id]))
    async def normalize_query(self,ctx,text):return NormalizedText(text=text,person_ids=[],ambiguous=False)
    async def load_staged_record(self,cap,ref):return self.records[ref.record_id]
    async def load_staged_artifacts(self,cap,key):return self.batches.get(key)
    async def stage_artifacts(self,cap,key,batch):
        saved=StagedArtifacts(artifact_key=key,batch=batch,lifecycle_revision=cap.lifecycle_revision,publication_generation=cap.publication_generation)
        if key in self.batches and self.batches[key]!=saved:raise DomainError('contract_violation')
        self.batches[key]=saved
        self.entries.update({e.id:e for e in batch.index_entries});self.events+=batch.proposed_history
        return saved
    async def published_context(self,cap):return WorkReadContext(project_id=self.project_id,job_id=cap.job_id,capability_id=cap.capability_id,snapshot=Snapshot(corpus_generation=1,privacy_generation=0))
    async def read_history(self,ctx,query,page):return HistoryPage(items=[e for e in self.events if e.topic_id==query.topic_id and e.scope==query.scope],next_cursor=None,coverage=Coverage(state='complete',records=[],limitations=[]))
    async def list_history_candidates(self,ctx,page):return HistoryPage(items=list(self.events),next_cursor=None,coverage=Coverage(state='complete',records=[],limitations=[]))
    async def prepare(self,cap,input):
        if input.idempotency_key in self.ops:return self.ops[input.idempotency_key]
        ticket=OperationTicket(operation=IndexOperation(id=str(uuid4()),job_id=cap.job_id,project_id=cap.project_id,action=input.action,entry_ids=input.entry_ids,lifecycle_revision=cap.lifecycle_revision,state='pending'),completion_token=str(uuid4()))
        self.ops[input.idempotency_key]=ticket;return ticket
    async def start(self,cap,operation_id):
        for t in self.ops.values():
            if t.operation.id==operation_id:t.operation.state='in_flight'
    async def report(self,ticket,outcome):ticket.operation.state=outcome.state
    async def list_operations(self,cap,page):return Page[IndexOperation](items=[t.operation for t in self.ops.values()],next_cursor=None)
    async def get_entries(self,cap,ids):return [self.entries[i] for i in ids if i in self.entries]
    async def lexical_candidates(self,ctx,query,filters,limit):
        words=query.lower().split();out=[]
        for e in self.entries.values():
            text=' '.join(s.text for s in self.records[e.record_id].spans).lower()
            if any(w in text for w in words):out.append(CandidateRef(entry_id=e.id,record_id=e.record_id,record_version=e.record_version,chunk_id=e.chunk_id,input_hash=e.input_hash,rank=len(out)+1))
        return out[:limit]
    async def validate_candidates(self,ctx,candidates,filters):
        good=[];bad=[]
        for c in candidates:
            e=self.entries.get(c.entry_id)
            if not e or e.input_hash!=c.input_hash or e.record_version!=c.record_version:bad.append(c.entry_id);continue
            r=self.records[e.record_id]
            if filters.original_doc_id and filters.original_doc_id!=r.original_doc_id:continue
            if filters.record_type and filters.record_type!=r.record_type:continue
            good.append(CanonicalCandidate(candidate=c,record=self.summary(r),snippet=r.spans[0].text,span_ids=e.span_ids))
        return CandidateCheck(eligible=good,rejected_entry_ids=bad)
    async def read_record(self,ctx,rid,page):
        r=self.records[rid];entries=[e for e in self.entries.values() if e.record_id==rid]
        offset=int(page.cursor or 0);selected=entries[offset:offset+page.limit]
        ids={s for e in selected for s in e.span_ids}
        memories=[m for b in self.batches.values() for m in b.batch.memories if any(d.record_id==rid for d in m.dependencies)]
        return MemoryPage(record_page=RecordPage(record=self.summary(r),spans=[s for s in r.spans if s.span_id in ids],returned_chunk_ids=[e.chunk_id for e in selected],total_chunks=len(entries),next_cursor=str(offset+len(selected)) if offset+len(selected)<len(entries) else None,complete=offset+len(selected)>=len(entries),snapshot=Snapshot(corpus_generation=1,privacy_generation=0)),memories=memories)
    async def make_receipt(self,ctx,ref):
        r=self.records[ref.record_id];spans={s.span_id:s for s in r.spans}
        return Receipt(id=stable_id(ref.record_id,*ref.span_ids),evidence_ref=ref,quote='\n'.join(spans[s].text for s in ref.span_ids),source_url=f'/projects/{ctx.project_id}/sources/{ref.record_id}?version=1&span={ref.span_ids[0]}',source_title=r.title,record_type=r.record_type,source_time=r.source_time,source_locations=[spans[s].source_location for s in ref.span_ids])
    async def read_memory(self,ctx,memory_id):
        return next(m for b in self.batches.values() for m in b.batch.memories if m.id==memory_id)
    async def expand_context(self,ctx,ref,before=2,after=2):
        r=self.records[ref.record_id]
        return SourcePage(record=self.summary(r),spans=r.spans,highlighted_span_ids=ref.span_ids,next_cursor=None,previous_cursor=None,snapshot=Snapshot(corpus_generation=1,privacy_generation=0))
