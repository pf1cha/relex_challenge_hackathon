from contextlib import asynccontextmanager
from types import MethodType

import pytest

from app.contracts.models import PageRequest, RequestContext
from app.evidence.service import EvidencePlatform


def context(role="member"):
    return RequestContext(
        user_id="user-1",
        session_id="session-1",
        project_id="project-1",
        role=role,
        access_revision=1,
        corpus_generation=3,
        privacy_generation=1,
    )


def record(record_id="record-1", document_id="document-1", source_time=None):
    return {
        "record_id": record_id,
        "original_doc_id": document_id,
        "record_version": 2,
        "title": "Shelf-life decision",
        "record_type": "email",
        "source_time": source_time or {"value": "2026-09-18T10:15:00Z", "precision": "instant", "timezone": "UTC"},
        "chunk_ids": ["chunk-1"],
        "spans": [{"span_id": "span 1"}],
        "published": True,
        "quarantined": False,
    }


def memory(memory_id, level, text, record_id="record-1"):
    return {
        "data": {
            "id": memory_id,
            "project_id": "project-1",
            "level": level,
            "kind": "record",
            "text": text,
            "dependencies": [{"record_id": record_id, "record_version": 2, "span_ids": ["span 1"]}],
            "generator_version": "test-model",
            "updated_at": "2026-09-18T10:20:00Z",
        },
        "valid": True,
    }


def platform(state):
    service = object.__new__(EvidencePlatform)
    service.secret = b"t" * 32

    @asynccontextmanager
    async def transaction(self, ctx, **_kwargs):
        yield None, state

    service.transaction = MethodType(transaction, service)
    return service


@pytest.mark.asyncio
async def test_timeline_exposes_both_summary_layers_and_processed_source_link():
    state = {
        "corpus_generation": 3,
        "privacy_generation": 1,
        "documents": {
            "document-1": {"id": "document-1", "ai_status": "active", "deleted": False},
        },
        "records": {"record-1": record()},
        "memories": {
            "memory-1": memory("memory-1", 1, "A short routing description."),
            "memory-2": memory("memory-2", 2, "A fuller evidence-backed summary."),
        },
    }

    page = await platform(state).get_timeline(context(), PageRequest(limit=100, cursor=None))

    assert page.next_cursor is None
    assert [item.model_dump(mode="json") for item in page.items] == [{
        "project_id": "project-1",
        "record_id": "record-1",
        "original_doc_id": "document-1",
        "record_version": 2,
        "title": "Shelf-life decision",
        "record_type": "email",
        "source_time": {"value": "2026-09-18T10:15:00Z", "precision": "instant", "timezone": "UTC"},
        "level1_summary": "A short routing description.",
        "level2_summary": "A fuller evidence-backed summary.",
        "processed_content_url": "/projects/project-1/sources/record-1?version=2&span=span%201",
    }]


@pytest.mark.asyncio
async def test_timeline_orders_known_source_times_and_keeps_unknown_dates_last():
    state = {
        "corpus_generation": 3,
        "privacy_generation": 1,
        "documents": {
            "document-1": {"id": "document-1", "ai_status": "active", "deleted": False},
        },
        "records": {
            "record-unknown": record("record-unknown", source_time={"value": None, "precision": "unknown", "timezone": None}),
            "record-late": record("record-late", source_time={"value": "2026-09-19", "precision": "day", "timezone": None}),
            "record-early": record("record-early", source_time={"value": "2026-08", "precision": "month", "timezone": None}),
        },
        "memories": {},
    }

    page = await platform(state).get_timeline(context(), PageRequest(limit=100, cursor=None))

    assert [item.record_id for item in page.items] == ["record-early", "record-late", "record-unknown"]


@pytest.mark.asyncio
async def test_timeline_respects_record_visibility_for_members_and_admins():
    active = record("record-active", "document-active")
    inactive = record("record-inactive", "document-inactive")
    deleted = record("record-deleted", "document-deleted")
    quarantined = {**record("record-quarantined", "document-active"), "quarantined": True}
    unpublished = {**record("record-unpublished", "document-active"), "published": False}
    state = {
        "corpus_generation": 3,
        "privacy_generation": 1,
        "documents": {
            "document-active": {"id": "document-active", "ai_status": "active", "deleted": False},
            "document-inactive": {"id": "document-inactive", "ai_status": "inactive", "deleted": False},
            "document-deleted": {"id": "document-deleted", "ai_status": "active", "deleted": True},
        },
        "records": {item["record_id"]: item for item in [active, inactive, deleted, quarantined, unpublished]},
        "memories": {},
    }
    service = platform(state)

    member_page = await service.get_timeline(context("member"), PageRequest(limit=100, cursor=None))
    admin_page = await service.get_timeline(context("admin"), PageRequest(limit=100, cursor=None))

    assert [item.record_id for item in member_page.items] == ["record-active"]
    assert [item.record_id for item in admin_page.items] == ["record-active", "record-inactive"]
