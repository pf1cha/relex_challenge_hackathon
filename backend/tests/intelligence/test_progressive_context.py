from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.contracts.errors import DomainError
from app.contracts.models import Memory, RecordSummary, SearchHit, SearchPage, Snapshot, SourceTime
from app.intelligence.tools import ToolSession


class Result:
    def __init__(self, **values):
        self.__dict__.update(values)

    def model_dump(self, mode="json"):
        return self.__dict__

    def model_dump_json(self):
        return str(self.__dict__)


class Reader:
    def __init__(self):
        self.reads = []

    async def read_record(self, ctx, record_id, page):
        self.reads.append(record_id)
        memory = Memory(
            id="memory-2", project_id=ctx.project_id, level=2, kind="record",
            text="Level 2 summary", dependencies=[], generator_version="test",
            updated_at=datetime.now(timezone.utc),
        )
        return Result(memories=[memory], record_page=Result())


class Owner:
    def __init__(self):
        self.reader = Reader()
        self.calls = []

    async def search_agent_memory(self, ctx, input):
        self.calls.append("memory")
        record = record_summary()
        return SearchPage(
            items=[SearchHit(record=record, description="Level 1 description", snippet="", matched_span_ids=[])],
            next_cursor=None, snapshot=ctx.snapshot,
        )

    async def search_sources(self, ctx, input):
        self.calls.append("sources")
        record = record_summary()
        return SearchPage(
            items=[SearchHit(record=record, description="Level 1 description", snippet="Canonical source", matched_span_ids=["span-1"])],
            next_cursor=None, snapshot=ctx.snapshot,
        )


def record_summary():
    return RecordSummary(
        record_id="record-1", original_doc_id="document-1", record_version=1,
        title="Launch meeting", record_type="transcript",
        source_time=SourceTime(value="2026-09-01", precision="day", timezone=None),
        total_chunks=1,
    )


def session():
    owner = Owner()
    ctx = SimpleNamespace(project_id="project-1", snapshot=Snapshot(corpus_generation=1, privacy_generation=1))
    limits = SimpleNamespace(tool_calls_per_phase=10, source_tokens_per_phase=100000, pages_per_phase=10)
    value = ToolSession(owner, ctx, limits, datetime.now(timezone.utc) + timedelta(seconds=10), 3)
    return owner, value


@pytest.mark.asyncio
async def test_discovery_exposes_only_level_1_and_does_not_read_sources():
    owner, value = session()

    await value.discover("launch date")

    assert owner.calls == ["memory"]
    assert owner.reader.reads == []
    result = value.results[0]["result"]
    assert result["items"][0]["description"] == "Level 1 description"
    assert result["items"][0]["snippet"] == ""
    assert result["items"][0]["matched_span_ids"] == []
    assert value.spans == {}
    assert value.retrieval_state() == {
        "layers_seen": ["L1"], "l1_record_ids": ["record-1"],
        "l2_record_ids": [], "source_searches": 0, "l3_record_ids": [],
        "remaining_search_rounds": 2,
    }


@pytest.mark.asyncio
async def test_level_2_and_level_3_require_explicit_tools():
    owner, value = session()
    await value.discover("launch date")

    memory = await value.call("read_memory", {"record_id": "record-1"})
    sources = await value.call("search_sources", {"query": "launch date"})

    assert memory.level == 2
    assert owner.reader.reads == ["record-1"]
    assert sources.items[0].snippet == "Canonical source"
    assert owner.calls == ["memory", "sources"]
    assert value.retrieval_state()["layers_seen"] == ["L1", "L2"]
    assert value.retrieval_state()["source_searches"] == 1


@pytest.mark.asyncio
async def test_level_3_record_read_requires_source_search_first():
    _, value = session()
    await value.discover("launch date")

    with pytest.raises(DomainError) as error:
        await value.call("read_record", {"record_id": "record-1"})

    assert error.value.code == "invalid_input"


@pytest.mark.asyncio
async def test_duplicate_tool_call_is_rejected_without_consuming_budget():
    _, value = session()
    await value.discover("launch date")
    await value.call("search_sources", {"query": "launch date"})
    calls = value.calls
    results = len(value.results)

    with pytest.raises(DomainError) as error:
        await value.call("search_sources", {"query": "launch date"})

    assert error.value.code == "invalid_input"
    assert value.calls == calls
    assert len(value.results) == results
