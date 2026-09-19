"""Fixed public errors; no provider messages or internal data are serialized."""
from fastapi.responses import JSONResponse

ERRORS = {
 "email_registered": (409, "This email is already registered. Sign in instead.", False),
 "unauthenticated": (401, "Please sign in.", False),
 "forbidden": (403, "Your project role cannot perform this action.", False),
 "csrf_failed": (403, "Request security validation failed.", False),
 "not_found": (404, "This resource is unavailable.", False),
 "evidence_changed": (409, "Project evidence changed. Retry the request.", True),
 "stale_cursor": (409, "The list changed. Reload it.", True),
 "write_barrier": (409, "Project cleanup is in progress. Retry when it finishes.", True),
 "request_in_progress": (409, "This request is still processing.", True),
 "idempotency_conflict": (409, "This request ID belongs to different input.", False),
 "last_admin": (409, "The project must retain an administrator.", False),
 "ambiguous_person": (409, "Select an unambiguous person identity.", False),
 "privacy_unresolved": (409, "Privacy processing could not complete: the source contains an unresolved identity or contextual privacy decision, or the privacy model returned an invalid plan. Resolve the privacy diagnostic, then retry.", True),
 "source_unavailable": (410, "This source version is unavailable. Regenerate the answer.", False),
 "answer_unavailable": (410, "This answer is unavailable. Regenerate it.", False),
 "invalid_input": (422, "The request input is invalid.", False),
 "unsupported_format": (422, "Upload supported UTF-8 text.", False),
 "upload_too_large": (413, "The upload exceeds the configured limit.", False),
 "provider_unavailable": (503, "The answer service is temporarily unavailable.", True),
 "dependency_unavailable": (503, "A required service is temporarily unavailable.", True),
 "contract_violation": (500, "The response could not be safely released.", False),
 "internal_error": (500, "The request could not be completed.", False),
}
def error_response(code):
    status, message, retryable = ERRORS.get(code, ERRORS["internal_error"])
    code = code if code in ERRORS else "internal_error"
    return JSONResponse({"error": {"code": code, "message": message, "retryable": retryable}},
                        status_code=status, headers={"Cache-Control": "no-store"})
