from __future__ import annotations
import base64
import hashlib
import hmac
import json
from app.contracts.models import CandidateRef, SearchPage, SearchHit, Snapshot
from app.contracts.errors import DomainError
from .providers import ProviderFailure
from .qdrant import IndexFailure

def snapshot(ctx):
    return ctx.snapshot if hasattr(ctx,"snapshot") else Snapshot(corpus_generation=ctx.corpus_generation,privacy_generation=ctx.privacy_generation)

class Retrieval:
    def __init__(self, reader, repository, provider, index, cursor_secret: bytes, *, rrf_k=60):
        if len(cursor_secret)<32:raise ValueError("Cursor signing key must be at least 32 bytes")
        self.reader,self.repository,self.provider,self.index=reader,repository,provider,index
        self.secret,self.rrf_k=cursor_secret,rrf_k

    def _encode(self, payload):
        data=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
        return base64.urlsafe_b64encode(data+hmac.digest(self.secret,data,"sha256")).decode()

    def _decode(self,cursor,binding):
        try:
            raw=base64.urlsafe_b64decode(cursor);data,mac=raw[:-32],raw[-32:]
            if not hmac.compare_digest(mac,hmac.digest(self.secret,data,"sha256")):raise ValueError()
            value=json.loads(data)
            if value["binding"]!=binding or type(value["offset"]) is not int or value["offset"]<0:raise ValueError()
            return value["offset"]
        except (ValueError,KeyError,TypeError):raise DomainError("stale_cursor") from None

    async def search(self,ctx,input,*,include_source=True):
        if not 1<=len(input.query)<=8000:raise DomainError("invalid_input")
        normalized=await self.reader.normalize_query(ctx,input.query)
        if normalized.ambiguous:raise DomainError("ambiguous_person")
        filters=input.filters
        if filters.date_from and filters.date_to and filters.date_from>filters.date_to:raise DomainError("invalid_input")
        binding=hashlib.sha256(json.dumps({"query":normalized.text,"filters":filters.model_dump(mode="json"),
            "context":ctx.model_dump(mode="json"),"limit":input.page.limit},sort_keys=True).encode()).hexdigest()
        offset=self._decode(input.page.cursor,binding) if input.page.cursor else 0
        lexical=await self.repository.lexical_candidates(ctx,normalized.text,filters,100)
        try:
            vector=(await self.provider.embed([normalized.text]))[0]
            await self.index.ensure(len(vector))
            semantic=await self.index.search(vector,ctx.project_id,100)
        except ProviderFailure:raise DomainError("provider_unavailable") from None
        except IndexFailure:raise DomainError("dependency_unavailable") from None
        candidates={};scores={}
        lists=[lexical,[]]
        for rank,row in enumerate(semantic,1):
            p=row.get("payload",{})
            if p.get("project_id")!=ctx.project_id:continue
            try:lists[1].append(CandidateRef(entry_id=str(row["id"]),record_id=p["record_id"],
                record_version=p["record_version"],chunk_id=p["chunk_id"],input_hash=p["input_hash"],rank=rank))
            except (KeyError,ValueError,TypeError):continue
        for rows in lists:
            seen=set()
            for rank,candidate in enumerate(rows,1):
                if candidate.entry_id in seen:continue
                seen.add(candidate.entry_id);candidates[candidate.entry_id]=candidate
                scores[candidate.entry_id]=scores.get(candidate.entry_id,0)+1/(self.rrf_k+rank)
        ordered=sorted(candidates.values(),key=lambda c:(-scores[c.entry_id],c.record_id,c.entry_id))
        # Canonical filtering occurs before parent deduplication and pagination.
        checked=[]
        for start in range(0,len(ordered),100):
            check=await self.repository.validate_candidates(ctx,ordered[start:start+100],filters)
            checked.extend(check.eligible)
        checked.sort(key=lambda c:(-scores[c.candidate.entry_id],c.record.record_id,c.candidate.entry_id))
        unique={}
        for item in checked:
            unique.setdefault(item.record.record_id,item)
        rows=list(unique.values());selected=rows[offset:offset+input.page.limit]
        next_offset=offset+len(selected)
        hits=[]
        for x in selected:
            from app.contracts.models import PageRequest
            memory=await self.reader.read_record(ctx,x.record.record_id,PageRequest(limit=1))
            description=next((m.text for m in memory.memories if m.level==1 and m.kind=="record"), "")
            hits.append(SearchHit(record=x.record,description=description,snippet=x.snippet if include_source else "",matched_span_ids=x.span_ids if include_source else []))
        return SearchPage(items=hits,
            next_cursor=self._encode({"binding":binding,"offset":next_offset}) if next_offset<len(rows) else None,
            snapshot=snapshot(ctx))
