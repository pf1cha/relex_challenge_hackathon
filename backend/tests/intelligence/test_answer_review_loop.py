from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.contracts.hashing import candidate_digest
from app.contracts.models import (
    AnswerInput, Claim, Coverage, NormalizedText, PageRequest, RetrievalAssessment,
    ReviewResult, ReviewedPayload, RuntimeLimits, SearchPage, Snapshot,
)
from app.intelligence.answering import Answers
from app.intelligence.maintenance import Maintenance
from app.intelligence.tools import ToolSession
from app.contracts.errors import DomainError


def test_stale_status_requires_retrieved_human_approved_history():
    answers=Answers()
    refs=[{"record_id":"record-1","record_version":1,"span_ids":["span-1"]}]
    session=SimpleNamespace(approved_history_events=[])
    with pytest.raises(DomainError) as error:
        answers._require_human_review("superseded",refs,session)
    assert error.value.code=="contract_violation"
    evidence=SimpleNamespace(record_id="record-1",record_version=1)
    session.approved_history_events.append(SimpleNamespace(kind="replacement",evidence=[evidence]))
    answers._require_human_review("superseded",refs,session)
    with pytest.raises(DomainError):
        answers._require_human_review("corrected",refs,session)


@pytest.mark.asyncio
async def test_ingestion_history_skips_stale_relationship_until_post_ingestion_analysis():
    maintenance=Maintenance()
    maintenance.retrieval=SimpleNamespace()
    cap=SimpleNamespace(project_id="project-1")
    record=SimpleNamespace(spans=[SimpleNamespace(span_id="span-1")])
    value={"events":[{"kind":"replacement","topic":"launch","scope":"date","text":"November replaces October",
        "span_ids":["span-1"],"effective_time":{"value":"2026-09-10","precision":"day","timezone":None},
        "prior_event_ids":[]}]}
    events=await maintenance._history(cap,record,value,datetime.now(timezone.utc),allow_consequential=False)
    assert events==[]


class NoActionProvider:
    settings=SimpleNamespace(model="test")
    def __init__(self,reasonable):self.reasonable=reasonable;self.calls=[]
    async def generate(self,role,system,payload):
        self.calls.append((role,payload))
        if role=="stale_no_action_review":return {"reasonable":self.reasonable,"reasoning":"No explicit current action." if self.reasonable else "An explicit cancellation requires investigation."}
        if len([item for item in self.calls if item[0]=="stale_analysis"])==1:return {"proposals":[]}
        return {"proposals":[{"record_id":"record-1","prior_event_id":"prior-1","kind":"cancellation","text":"Cancelled","span_ids":["span-1"],"effective_time":{"value":None,"precision":"unknown","timezone":None}}]}


class NoActionSession:
    def __init__(self):self.results=[];self.deadline=datetime.now(timezone.utc)+timedelta(seconds=10)
    def coverage(self):return Coverage(state="insufficient",records=[],limitations=[])
    def retrieval_state(self):return {}


@pytest.mark.asyncio
async def test_reasonable_no_stale_action_is_accepted_after_lightweight_review():
    maintenance=Maintenance();maintenance.provider=NoActionProvider(True);maintenance._generate=Answers._generate.__get__(maintenance)
    memory=SimpleNamespace(model_dump=lambda mode="json":{"text":"Current unless later replaced."})

    result=await maintenance._stale_agent(NoActionSession(),[memory],{"record-1"},[])

    assert result=={"proposals":[]}
    assert [role for role,_ in maintenance.provider.calls]==["stale_analysis","stale_no_action_review"]


@pytest.mark.asyncio
async def test_unreasonable_no_stale_action_gets_one_bounded_retry():
    maintenance=Maintenance();maintenance.provider=NoActionProvider(False);maintenance._generate=Answers._generate.__get__(maintenance)
    memory=SimpleNamespace(model_dump=lambda mode="json":{"text":"The budget is explicitly cancelled."})

    prior=SimpleNamespace(id="prior-1",model_dump=lambda mode="json":{"id":"prior-1"})
    result=await maintenance._stale_agent(NoActionSession(),[memory],{"record-1"},[prior])

    assert result["proposals"][0]["kind"]=="cancellation"
    assert maintenance.provider.calls[-1][1]["retrieval_guidance"]["code"]=="unreasonable_no_action"


class ShallowProvider:
    settings = SimpleNamespace(model="test")

    def __init__(self):
        self.requests = []


    async def generate(self, role, system, payload):
        self.requests.append(payload)
        if len(self.requests) == 1:
            return {"claims": [], "cannot_establish": "no_evidence"}
        if len(self.requests) == 2:
            assert payload["retrieval_guidance"]["requires_source_search"] is True
            return {"tools": [{"name": "search_sources", "arguments": {"query": "launch"}}]}
        return {"claims": [], "cannot_establish": "no_evidence"}


class DiscoveryOwner(Answers):
    def __init__(self):
        self.provider = ShallowProvider()

    async def search_agent_memory(self, ctx, input):
        record = SimpleNamespace(record_id="record-1")
        hit = SimpleNamespace(record=record)
        result = SimpleNamespace(items=[hit], next_cursor=None, snapshot=ctx.snapshot)
        result.model_dump_json = lambda: "discovery"
        result.model_dump = lambda mode="json": {"items": [{"record": {"record_id": "record-1"}}]}
        return result

    async def search_sources(self, ctx, input):
        return SearchPage(items=[], next_cursor=None, snapshot=ctx.snapshot)


@pytest.mark.asyncio
async def test_shallow_answer_is_prompted_to_search_sources_before_finalizing():
    owner = DiscoveryOwner()
    ctx = SimpleNamespace(project_id="project-1", snapshot=Snapshot(corpus_generation=1, privacy_generation=0))
    limits = SimpleNamespace(tool_calls_per_phase=10, source_tokens_per_phase=10000, pages_per_phase=10)
    session = ToolSession(owner, ctx, limits, datetime.now(timezone.utc) + timedelta(seconds=10), 3)
    await session.discover("launch")

    result = await owner._agent("answer", session, {"question": "launch"})

    assert result["cannot_establish"] == "no_evidence"
    assert [item["tool"] for item in session.trace] == ["search_memory", "search_sources"]
    assert len(owner.provider.requests) == 3


class InvalidSequenceProvider:
    settings = SimpleNamespace(model="test")

    def __init__(self):
        self.requests = []

    async def generate(self, role, system, payload):
        self.requests.append(payload)
        if len(self.requests) == 1:
            return {"tools": [{"name": "read_record", "arguments": {"record_id": "record-1"}}]}
        if len(self.requests) == 2:
            assert payload["retrieval_guidance"]["code"] == "invalid_tool_sequence"
            assert payload["retrieval_guidance"]["requires_source_search"] is True
            return {"tools": [{"name": "search_sources", "arguments": {
                "query": "launch", "filters": {"record_id": "record-1"}}}]}
        if len(self.requests) == 3:
            assert payload["retrieval_guidance"]["code"] == "invalid_tool_sequence"
            assert payload["retrieval_guidance"]["requires_source_search"] is False
            return {"tools": [{"name": "search_sources", "arguments": {"query": "launch"}}]}
        return {"claims": [], "cannot_establish": "no_evidence"}


@pytest.mark.asyncio
async def test_model_generated_invalid_tool_sequence_is_reprompted():
    owner = DiscoveryOwner()
    owner.provider = InvalidSequenceProvider()
    ctx = SimpleNamespace(project_id="project-1", snapshot=Snapshot(corpus_generation=1, privacy_generation=0))
    limits = SimpleNamespace(tool_calls_per_phase=10, source_tokens_per_phase=10000, pages_per_phase=10)
    session = ToolSession(owner, ctx, limits, datetime.now(timezone.utc) + timedelta(seconds=10), 3)
    await session.discover("launch")

    result = await owner._agent("answer", session, {"question": "launch"})

    assert result == {"claims": [], "cannot_establish": "no_evidence"}
    assert [item["tool"] for item in session.trace] == ["search_memory", "search_sources"]
    assert len(owner.provider.requests) == 4


class UnreadEvidenceProvider:
    settings = SimpleNamespace(model="test")

    def __init__(self):
        self.requests = []
        self.final = {"claims": [{"text": "Supported claim", "evidence": [{
            "record_id": "record-1", "record_version": 1, "span_ids": ["span-1"]}]}],
            "cannot_establish": None}

    async def generate(self, role, system, payload):
        self.requests.append(payload)
        if len(self.requests) == 1:
            return self.final
        if len(self.requests) == 2:
            assert payload["retrieval_guidance"]["code"] == "unread_evidence"
            assert payload["retrieval_guidance"]["suggested_record_ids"] == ["record-1"]
            return {"tools": [{"name": "read_record", "arguments": {"record_id": "record-1"}}]}
        return self.final


class CitationSession:
    def __init__(self):
        self.results = []
        self.discovered_records = {"record-0", "record-1"}
        self.source_records = {"record-0", "record-1"}
        self.source_searches = 1
        self.searches = 1
        self.round_limit = 3
        self.spans = {("record-0", 1): {"span-0": SimpleNamespace(ordinal=1)}}
        self.calls = []

    def coverage(self):
        return Coverage(state="insufficient", records=[], limitations=[])

    def retrieval_state(self):
        return {}

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        self.spans[("record-1", 1)] = {"span-1": SimpleNamespace(ordinal=1)}


@pytest.mark.asyncio
async def test_final_answer_with_unread_evidence_is_reprompted_to_read_record():
    owner = Answers()
    owner.provider = UnreadEvidenceProvider()
    session = CitationSession()
    session.deadline = datetime.now(timezone.utc) + timedelta(seconds=10)

    result = await owner._agent("answer", session, {"question": "launch"})

    assert result == owner.provider.final
    assert session.calls == [("read_record", {"record_id": "record-1"})]
    assert len(owner.provider.requests) == 3


class TwoRepairAnswers(Answers):
    def __init__(self):
        self.limits = RuntimeLimits(answer_search_rounds=3, repair_search_rounds=1,
            reviewer_passes=3, reviewer_search_rounds=3, tool_calls_per_phase=10,
            pages_per_phase=10, source_tokens_per_phase=10000, request_deadline_seconds=30)
        self.traces = []
        self.review_count = 0
        self.repair_count = 0

    async def search_agent_memory(self, ctx, input):
        return SearchPage(items=[], next_cursor=None,
            snapshot=Snapshot(corpus_generation=ctx.corpus_generation, privacy_generation=ctx.privacy_generation))

    async def _agent(self, role, session, payload):
        if role == "repair":
            self.repair_count += 1
        return {"claims": [], "cannot_establish": None}

    async def _draft(self, ctx, raw, session):
        claim = Claim(id=f"claim-{self.repair_count}", text="Supported claim", receipt_ids=[],
            status=None, scope=None, effective_at=None)
        return ReviewedPayload(claims=[claim], receipts=[], dependencies=[],
            coverage=Coverage(state="complete", records=[], limitations=[]), cannot_establish=None,
            snapshot=Snapshot(corpus_generation=ctx.corpus_generation, privacy_generation=ctx.privacy_generation))

    async def _review(self, question, payload, session, deadline):
        self.review_count += 1
        sufficient = self.review_count == 3
        assessment = RetrievalAssessment(verdict="sufficient" if sufficient else "insufficient",
            missing_context=[] if sufficient else ["Check later revisions"],
            suggested_queries=[] if sufficient else ["launch corrections"], suggested_record_ids=[])
        result = ReviewResult(claim_id=payload.claims[0].id, verdict="pass" if sufficient else "fail",
            reason_code="supported" if sufficient else "incomplete_coverage", receipt_ids=[],
            repair_request=None if sufficient else "Retrieve later revisions.",
            candidate_digest=candidate_digest(payload))
        return payload, assessment, [result]


@pytest.mark.asyncio
async def test_two_answer_repairs_are_followed_by_a_third_review():
    owner = TwoRepairAnswers()
    ctx = SimpleNamespace(project_id="project-1", corpus_generation=1, privacy_generation=0)
    result = await owner.answer(ctx, AnswerInput(question=NormalizedText(text="launch", person_ids=[], ambiguous=False),
        history=[], request_id="request", conversation_id="conversation",
        deadline=datetime.now(timezone.utc) + timedelta(seconds=30)))

    assert owner.review_count == 3
    assert owner.repair_count == 2
    assert [trace["attempt"] for trace in owner.traces if trace["phase"] == "repair"] == [1, 2]
    assert result.retrieval_review.verdict == "sufficient"
    assert len(result.claims) == 1
