from typing import Literal
ErrorCode = Literal["email_registered", "unauthenticated", "forbidden", "csrf_failed", "not_found", "evidence_changed", "stale_cursor", "write_barrier", "request_in_progress", "idempotency_conflict", "last_admin", "ambiguous_person", "privacy_unresolved", "source_unavailable", "answer_unavailable", "invalid_input", "unsupported_format", "upload_too_large", "provider_unavailable", "dependency_unavailable", "contract_violation", "internal_error", "lease_lost", "capability_denied", "index_outcome_unknown"]
RETRYABLE = {"evidence_changed", "stale_cursor", "write_barrier", "request_in_progress", "provider_unavailable", "privacy_unresolved", "dependency_unavailable", "lease_lost", "index_outcome_unknown"}
HTTP_STATUS = {"email_registered":409, "unauthenticated":401, "forbidden":403, "csrf_failed":403, "not_found":404, "source_unavailable":410, "answer_unavailable":410, "invalid_input":422, "unsupported_format":422, "upload_too_large":413, "provider_unavailable":503, "dependency_unavailable":503}
HTTP_STATUS.update({key:409 for key in ["evidence_changed","stale_cursor","write_barrier","request_in_progress","idempotency_conflict","last_admin","ambiguous_person","privacy_unresolved"]})
class DomainError(Exception):
    def __init__(self, code: ErrorCode, retryable: bool | None = None):
        self.code = code
        self.retryable = code in RETRYABLE if retryable is None else retryable
        super().__init__(code)
