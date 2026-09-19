"""Stable, bounded source slices; receipts continue to cite whole canonical spans."""
from hashlib import sha256
from uuid import uuid5, NAMESPACE_URL
from app.contracts.models import ChunkDescriptor, SpanSlice

def stable_id(*parts):
    return str(uuid5(NAMESPACE_URL,"relex:intelligence:"+":".join(map(str,parts))))

def chunk_text(chunk, spans):
    by_id={s.span_id:s.text for s in spans}
    return "\n".join(by_id[s.span_id][s.start:s.end] for s in chunk.slices)

def embedding_input(chunk, memories, spans):
    by_id={m.id:m for m in memories}
    return by_id[chunk.level1_memory_id].text+"\n\n"+by_id[chunk.level2_memory_id].text+"\n\n"+chunk_text(chunk,spans)

def make_chunks(record, level1_id, level2_id, memories, *, max_chars=1800, overlap_chars=200):
    if max_chars <= overlap_chars or overlap_chars < 0:
        raise ValueError("Invalid chunk bounds")
    groups=[]; current=[]; size=0
    for span in sorted(record.spans,key=lambda s:s.ordinal):
        start=0
        if not span.text:
            continue
        while start<len(span.text):
            end=min(len(span.text),start+max_chars)
            part=SpanSlice(span_id=span.span_id,start=start,end=end)
            if current and size+(end-start)+1>max_chars:
                groups.append(current);current=[];size=0
            current.append(part);size+=end-start+1
            if end<len(span.text):
                groups.append(current);current=[];size=0
                start=end-overlap_chars
            else:break
    if current:groups.append(current)
    chunks=[]
    for ordinal,slices in enumerate(groups):
        chunk=ChunkDescriptor(id=stable_id(record.record_id,record.record_version,"chunk",ordinal),
            record_id=record.record_id,record_version=record.record_version,ordinal=ordinal,slices=slices,
            level1_memory_id=level1_id,level2_memory_id=level2_id,input_hash="0"*64)
        chunk.input_hash=sha256(embedding_input(chunk,memories,record.spans).encode()).hexdigest()
        chunks.append(chunk)
    return chunks
