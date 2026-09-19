"""Pure contract encoders. Never normalize text or reorder arrays."""
import hashlib
import json
import uuid
from .models import ReviewedPayload
def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
def candidate_digest(candidate):
    data = candidate.model_dump(mode="json") if hasattr(candidate, "model_dump") else candidate
    payload = {key:data[key] for key in ("claims","receipts","dependencies","coverage","cannot_establish","snapshot")}
    return hashlib.sha256(compact(payload).encode()).hexdigest()
def make_entry_id(project_id, record_id, record_version, chunk_id, input_hash, embedding_model, embedding_dimension):
    args=[project_id,record_id,record_version,chunk_id,input_hash,embedding_model,embedding_dimension]
    return str(uuid.uuid5(uuid.NAMESPACE_URL,"relex:entry:v4:"+compact(args)))
def artifact_key(kind, *ids):
    if kind == "record" and len(ids)==2 or kind == "aggregate" and len(ids)==1:
        return compact([kind,*ids])
    raise ValueError("invalid artifact key")
def record_artifact_key(record_id, record_version):
    return artifact_key("record", record_id, record_version)
def aggregate_artifact_key(plan_id):
    return artifact_key("aggregate", plan_id)
