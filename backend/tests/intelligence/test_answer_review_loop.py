from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.contracts.hashing import candidate_digest
from app.contracts.models import (
    AnswerInput, Claim, Coverage, NormalizedText, PageRequest, RetrievalAssessment,
    ReviewResult, ReviewedPayload, RuntimeLimits, SearchPage, Snapshot,
)
from app.intelligence.answering import Answers
from app.intelligence.tools import ToolSession


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
