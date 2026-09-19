"""Adapter-driven contract checks; development aids, not live acceptance."""
from app.contracts.errors import DomainError
from app.contracts.hashing import candidate_digest
CONTRACT_REVISION = 5
CASES = {
"CT-01":"revoked session cannot release", "CT-02":"wrong project or owner denied",
"CT-03":"ordered chunk paging and cursor binding", "CT-04":"stale candidates withheld",
"CT-05":"quote and digest binding", "CT-06":"matching request replay",
"CT-07":"different input conflicts", "CT-08":"changed receipt unavailable",
"CT-09":"unknown upsert outstanding", "CT-10":"late outcome cannot publish",
"CT-11":"pending overview empty", "CT-12":"provider failure withholds claims",
"CT-13":"malformed artifacts rejected", "CT-14":"inert fixture app import",
"CT-15":"same-name identities distinct", "CT-16":"erasure write barrier",
"CT-17":"durable exact checkpoint reload",
}
async def expect_error(code, operation):
    try:
        await operation()
    except DomainError as error:
        assert error.code == code
    else:
        raise AssertionError("Expected safe domain error: "+code)
def assert_review_binding(candidate):
    assert candidate_digest(candidate) == candidate.candidate_digest
    if candidate.omission_proof is None:
        assert all(r.candidate_digest == candidate.candidate_digest for r in candidate.review_results)
def assert_hidden_overview(overview):
    if overview.state != "ready":
        assert overview.claims == [] and overview.receipts == []
