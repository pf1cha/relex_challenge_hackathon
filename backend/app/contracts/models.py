from __future__ import annotations
from datetime import datetime, date, timezone
from typing import Annotated, Generic, TypeVar, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, StrictBool, BeforeValidator

def _instant(v):
    if isinstance(v, str): v = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if not isinstance(v, datetime) or v.tzinfo is None: raise ValueError("offset timestamp required")
    return v.astimezone(timezone.utc)
Id = Annotated[str, Field(min_length=1, max_length=128)]
Version = Annotated[StrictInt, Field(ge=1)]
Revision = Annotated[StrictInt, Field(ge=0)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Instant = Annotated[datetime, BeforeValidator(_instant)]
Date = date
class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
T=TypeVar("T")
class PageRequest(DTO):
    cursor: str | None = None
    limit: Annotated[StrictInt, Field(ge=1, le=100)] = 25
class Page(DTO, Generic[T]):
    items: list[T]
    next_cursor: str | None
Role = Literal['member', 'admin']
RecordType = Literal['email', 'transcript', 'report', 'specification']
Purpose = Literal['answer_evidence', 'admin_source_preview']
JobKind = Literal['ingest', 'activate', 'deactivate', 'delete_document', 'erase_person', 'rebuild_aggregate', 'reconcile']
JobState = Literal['pending', 'running', 'completed', 'failed']
JobStage = Literal['received', 'parsed', 'privacy_ready', 'extracted', 'indexed', 'published', 'invalidating', 'inventory', 'draining', 'sanitizing', 'rebuilding', 'removing_index', 'verifying', 'done']

class Snapshot(DTO):
    corpus_generation: Revision
    privacy_generation: Revision

class SessionPrincipal(DTO):
    user_id: Id
    session_id: Id
    expires_at: Instant

class RequestContext(DTO):
    user_id: Id
    session_id: Id
    project_id: Id
    role: Role
    access_revision: Revision
    corpus_generation: Revision
    privacy_generation: Revision

class SourceTime(DTO):
    value: str | None
    precision: Literal['unknown', 'year', 'month', 'day', 'instant']
    timezone: str | None

class Me(DTO):
    user_id: Id
    display_name: str
    csrf_token: str
    expires_at: Instant

class Project(DTO):
    id: Id
    name: str
    role: Role

class Document(DTO):
    id: Id
    project_id: Id
    title: str
    record_type: RecordType
    ai_status: Literal['active', 'inactive']
    processing_state: Literal['pending', 'running', 'completed', 'failed']
    record_count: StrictInt
    records_url: str
    latest_job_id: Id | None
    created_at: Instant
    updated_at: Instant

class RecordSummary(DTO):
    record_id: Id
    original_doc_id: Id
    record_version: Version
    title: str
    record_type: RecordType
    source_time: SourceTime
    total_chunks: StrictInt

class SourceLocation(DTO):
    line_start: StrictInt | None
    line_end: StrictInt | None
    paragraph: StrictInt | None
    message_ordinal: StrictInt | None
    turn_ordinal: StrictInt | None
    timestamp_label: str | None

class Span(DTO):
    span_id: Id
    ordinal: StrictInt
    text: str
    source_location: SourceLocation

class EvidenceRef(DTO):
    project_id: Id
    original_doc_id: Id
    record_id: Id
    record_version: Version
    span_ids: list[Id]

class Dependency(DTO):
    record_id: Id
    record_version: Version
    span_ids: list[Id]

class RecordPage(DTO):
    record: RecordSummary
    spans: list[Span]
    returned_chunk_ids: list[Id]
    total_chunks: StrictInt
    next_cursor: str | None
    complete: StrictBool
    snapshot: Snapshot

class SourcePage(DTO):
    record: RecordSummary
    spans: list[Span]
    highlighted_span_ids: list[Id]
    next_cursor: str | None
    previous_cursor: str | None
    snapshot: Snapshot

class Receipt(DTO):
    id: Id
    evidence_ref: EvidenceRef
    quote: str
    source_url: str
    source_title: str
    record_type: RecordType
    source_time: SourceTime
    source_locations: list[SourceLocation]

class Claim(DTO):
    id: Id
    text: str
    receipt_ids: list[Id]
    status: Literal['suggestion', 'commitment', 'superseded', 'corrected', 'conflict', 'unknown'] | None
    scope: str | None
    effective_at: SourceTime | None

class Coverage(DTO):
    state: Literal['complete', 'partial', 'insufficient']
    records: list[RecordCoverage]
    limitations: list[Limitation]

class RecordCoverage(DTO):
    record_id: Id
    record_version: Version
    total_chunks: StrictInt
    supplied_chunk_ids: list[Id]
    complete: StrictBool

class Limitation(DTO):
    code: Literal['no_evidence', 'unread_chunks', 'history_incomplete', 'conflicting_evidence', 'budget_exhausted', 'ambiguous_person', 'unknown_effective_time']
    record_ids: list[Id]

class Answer(DTO):
    id: Id
    conversation_id: Id
    request_id: Id
    claims: list[Claim]
    receipts: list[Receipt]
    coverage: Coverage
    cannot_establish: Literal['no_evidence', 'incomplete_coverage', 'unresolved_conflict', 'ambiguous_person', 'review_rejected'] | None
    snapshot: Snapshot
    created_at: Instant

class Conversation(DTO):
    id: Id
    project_id: Id
    owner_user_id: Id
    title: str
    created_at: Instant
    updated_at: Instant

class Message(DTO):
    id: Id
    conversation_id: Id
    role: Literal['user', 'assistant']
    state: Literal['available', 'pending', 'unavailable', 'failed']
    text: str | None
    answer_id: Id | None
    unavailable_reason: str | None
    created_at: Instant

class Job(DTO):
    id: Id
    project_id: Id
    kind: JobKind
    state: JobState
    stage: JobStage
    counts: dict[str, StrictInt]
    error_code: str | None
    retryable: StrictBool
    created_at: Instant
    updated_at: Instant

class ProjectStatus(DTO):
    project_id: Id
    eligible_documents: StrictInt
    eligible_records: StrictInt
    operational_job_counts: dict[JobState, StrictInt] | None
    write_barrier: StrictBool
    snapshot: Snapshot

class Overview(DTO):
    state: Literal['pending', 'ready', 'failed', 'unavailable']
    id: Id | None
    claims: list[Claim]
    receipts: list[Receipt]
    coverage: Coverage | None
    snapshot: Snapshot
    error_code: str | None

class Member(DTO):
    user_id: Id
    display_name: str
    role: Role
    granted_at: Instant

class Person(DTO):
    id: Id
    display_name: str
    kind: Literal['client', 'employee']
    contacts: list[Contact]
    state: Literal['active', 'erasing']

class Contact(DTO):
    kind: Literal['email', 'phone', 'postal_address']
    value: str

class FilterOptions(DTO):
    record_types: list[RecordType]
    documents: list[Option]
    topics: list[Option]
    people: list[Option]

class Option(DTO):
    id: Id
    label: str

class LoginResult(DTO):
    session_token: str
    me: Me

class UploadInput(DTO):
    filename: str
    record_type: RecordType
    content: bytes

class SourceRequest(DTO):
    record_id: Id
    version: Version
    span_id: Id
    cursor: str | None = None
    limit: StrictInt | None = None

class PersonInput(DTO):
    person_id: Id | None = None
    display_name: str
    kind: Literal['client', 'employee']
    contacts: list[Contact]

class ChatInput(DTO):
    question: str
    conversation_id: Id
    request_id: Id

class ChatAttempt(DTO):
    attempt_id: Id
    request_id: Id
    conversation_id: Id
    input_hash: Digest
    lease_token: str
    deadline: Instant

class AnswerInput(DTO):
    question: NormalizedText
    history: list[HistoryTurn]
    request_id: Id
    conversation_id: Id
    deadline: Instant

class NormalizedText(DTO):
    text: str
    person_ids: list[Id]
    ambiguous: StrictBool

class RuntimeLimits(DTO):
    answer_search_rounds: StrictInt
    repair_search_rounds: StrictInt
    reviewer_passes: StrictInt
    reviewer_search_rounds: StrictInt
    tool_calls_per_phase: StrictInt
    pages_per_phase: StrictInt
    source_tokens_per_phase: StrictInt
    request_deadline_seconds: StrictInt

class HistoryTurn(DTO):
    message_id: Id
    role: Literal['user', 'assistant']
    text: str

class Memory(DTO):
    id: Id
    project_id: Id
    level: Literal[1, 2]
    kind: Literal['record', 'topic', 'overview']
    text: str
    dependencies: list[Dependency]
    generator_version: str
    updated_at: Instant

class MemoryPage(DTO):
    record_page: RecordPage
    memories: list[Memory]

class WorkReadContext(DTO):
    project_id: Id
    job_id: Id
    capability_id: Id
    snapshot: Snapshot

class SearchFilters(DTO):
    date_from: Date | None = None
    date_to: Date | None = None
    record_type: RecordType | None = None
    original_doc_id: Id | None = None
    topic_id: Id | None = None
    person_id: Id | None = None

class SearchInput(DTO):
    query: str
    filters: SearchFilters
    page: Literal['PageRequest']

class CandidateRef(DTO):
    entry_id: Id
    record_id: Id
    record_version: Version
    chunk_id: Id
    input_hash: Digest
    rank: StrictInt

class CanonicalCandidate(DTO):
    candidate: CandidateRef
    record: RecordSummary
    snippet: str
    span_ids: list[Id]

class CandidateCheck(DTO):
    eligible: list[CanonicalCandidate]
    rejected_entry_ids: list[Id]

class HistoryQuery(DTO):
    topic_id: Id
    scope: str
    as_of: SourceTime | None

class HistoryEvent(DTO):
    id: Id
    topic_id: Id
    scope: str
    kind: Literal['suggestion', 'commitment', 'replacement', 'cancellation', 'correction', 'reinstatement', 'conflict']
    text: str
    source_time: SourceTime
    effective_time: SourceTime
    learned_at: Instant
    evidence: list[EvidenceRef]
    prior_event_ids: list[Id]
    review_state: Literal['pending', 'passed', 'failed']

class HistoryPage(DTO):
    items: list[HistoryEvent]
    next_cursor: str | None
    coverage: Coverage

class SearchHit(DTO):
    record: RecordSummary
    description: str
    snippet: str
    matched_span_ids: list[Id]

class SearchPage(DTO):
    items: list[SearchHit]
    next_cursor: str | None
    snapshot: Snapshot

class ReviewResult(DTO):
    claim_id: Id
    verdict: Literal['pass', 'fail']
    reason_code: Literal['supported', 'missing_support', 'attribution_mismatch', 'proposal_as_agreement', 'missing_condition', 'stale_as_current', 'citation_mismatch', 'incomplete_coverage']
    receipt_ids: list[Id]
    repair_request: str | None
    candidate_digest: Digest

class ReviewedCandidate(DTO):
    claims: list[Claim]
    receipts: list[Receipt]
    dependencies: list[Dependency]
    coverage: Coverage
    cannot_establish: Literal['no_evidence', 'incomplete_coverage', 'unresolved_conflict', 'ambiguous_person', 'review_rejected'] | None
    snapshot: Snapshot
    review_results: list[ReviewResult]
    candidate_digest: Digest
    omission_proof: OmissionProof | None

class OmissionProof(DTO):
    reviewed: ReviewedPayload
    review_results: list[ReviewResult]
    reviewed_digest: Digest

class ReviewedPayload(DTO):
    claims: list[Claim]
    receipts: list[Receipt]
    dependencies: list[Dependency]
    coverage: Coverage
    cannot_establish: Literal['no_evidence', 'incomplete_coverage', 'unresolved_conflict', 'ambiguous_person', 'review_rejected'] | None
    snapshot: Snapshot

class RecordVersionRef(DTO):
    record_id: Id
    record_version: Version

class JobCapability(DTO):
    capability_id: Id
    job_id: Id
    project_id: Id
    lease_token: str
    lifecycle_revision: Revision
    allowed_stage: JobStage
    allowed_record_versions: list[RecordVersionRef]
    publication_generation: Revision
    expires_at: Instant

class StagedRecord(DTO):
    project_id: Id
    original_doc_id: Id
    record_id: Id
    record_version: Version
    record_type: RecordType
    title: str
    source_time: SourceTime
    spans: list[Span]
    person_ids: list[Id]
    duplicate_of: Id | None

class SpanSlice(DTO):
    span_id: Id
    start: StrictInt
    end: StrictInt

class ChunkDescriptor(DTO):
    id: Id
    record_id: Id
    record_version: Version
    ordinal: StrictInt
    slices: list[SpanSlice]
    level1_memory_id: Id
    level2_memory_id: Id
    input_hash: Digest

class IndexEntry(DTO):
    id: Id
    project_id: Id
    original_doc_id: Id
    record_id: Id
    record_version: Version
    chunk_id: Id
    span_ids: list[Id]
    topic_ids: list[Id]
    person_ids: list[Id]
    source_time: SourceTime
    publication_generation: Revision
    input_hash: Digest
    embedding_model: str
    embedding_dimension: StrictInt

class ArtifactBatch(DTO):
    batch_id: Id
    job_id: Id
    project_id: Id
    memories: list[Memory]
    chunks: list[ChunkDescriptor]
    proposed_history: list[HistoryEvent]
    index_entries: list[IndexEntry]
    dependencies: list[Dependency]

class RebuildPlan(DTO):
    id: Id
    project_id: Id
    record_versions: list[RecordVersionRef]
    memory_ids: list[Id]
    obsolete_entry_ids: list[Id]
    dependencies: list[Dependency]
    snapshot: Snapshot

class MaintenanceResult(DTO):
    batch_id: Id | None
    operation_ids: list[Id]
    changed_entry_ids: list[Id]
    removed_entry_ids: list[Id]
    unchanged_entry_ids: list[Id]

class StagedArtifacts(DTO):
    artifact_key: str
    batch: ArtifactBatch
    lifecycle_revision: Revision
    publication_generation: Revision

class OverviewCandidate(DTO):
    memory_id: Id
    candidate: ReviewedCandidate

class JobLease(DTO):
    job: Job
    work: WorkPlan
    lease_token: str
    expires_at: Instant

class WorkPlan(DTO):
    document_ids: list[Id]
    person_ids: list[Id]
    record_versions: list[RecordVersionRef]
    rebuild_plan_ids: list[Id]
    removal_entry_ids: list[Id]

class ReconciliationReport(DTO):
    checked_entry_ids: list[Id]
    missing_entry_ids: list[Id]
    obsolete_entry_ids: list[Id]
    unresolved_operation_ids: list[Id]
    corrective_operation_ids: list[Id]

class IndexOperationInput(DTO):
    idempotency_key: str
    action: Literal['upsert', 'delete']
    entries: list[IndexEntry]
    entry_ids: list[Id]

class IndexOperation(DTO):
    id: Id
    job_id: Id
    project_id: Id
    action: Literal['upsert', 'delete']
    entry_ids: list[Id]
    lifecycle_revision: Revision
    state: Literal['pending', 'in_flight', 'succeeded', 'failed', 'unknown']

class OperationTicket(DTO):
    operation: IndexOperation
    completion_token: str

class IndexOutcome(DTO):
    state: Literal['succeeded', 'failed', 'unknown']
    completed_entry_ids: list[Id]
    error_code: str | None
    observed_at: Instant

class PrivacyDetectionInput(DTO):
    project_id: Id
    record_id: Id
    text: str

class Detection(DTO):
    start: StrictInt
    end: StrictInt
    kind: Literal['name', 'email', 'phone', 'postal_address', 'private_discussion']
    identity_hint: str | None
    confidence: Literal['certain', 'uncertain']

class PrivacyDetectionResult(DTO):
    detections: list[Detection]
    unresolved: StrictBool

ReadContext = RequestContext | WorkReadContext
class BeginChatReady(DTO):
    state: Literal["ready"] = "ready"
    attempt: ChatAttempt
    input: AnswerInput
class BeginChatReplay(DTO):
    state: Literal["replay"] = "replay"
    answer: Answer
BeginChatResult = Annotated[Union[BeginChatReady, BeginChatReplay], Field(discriminator="state")]
for _model in list(globals().values()):
    if isinstance(_model, type) and issubclass(_model, DTO): _model.model_rebuild()
