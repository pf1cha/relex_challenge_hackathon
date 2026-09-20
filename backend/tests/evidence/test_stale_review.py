from contextlib import asynccontextmanager
from types import MethodType

import pytest

from app.contracts.models import HistoryQuery, PageRequest, RequestContext
from app.contracts.errors import DomainError
from app.evidence.service import EvidencePlatform


def context():
    return RequestContext(user_id="admin-1",session_id="session-1",project_id="project-1",
        role="admin",access_revision=1,corpus_generation=3,privacy_generation=1)


def evidence(record_id,span_id):
    return {"project_id":"project-1","original_doc_id":"document-"+record_id,
        "record_id":record_id,"record_version":1,"span_ids":[span_id]}


def record(record_id,title,span_id,text,date):
    return {"record_id":record_id,"original_doc_id":"document-"+record_id,"record_version":1,
        "title":title,"record_type":"report","source_time":{"value":date,"precision":"day","timezone":None},
        "chunk_ids":[],"spans":[{"span_id":span_id,"ordinal":0,"text":text,
            "source_location":{"line_start":1,"line_end":1,"paragraph":None,"message_ordinal":None,"turn_ordinal":None,"timestamp_label":None}}],
        "person_ids":[],"entry_ids":[],"published":True,"quarantined":False,"created_at":date+"T00:00:00Z"}


def event(event_id,kind,text,record_id,span_id,prior_ids=None,human="not_required",review="passed",reason=None):
    return {"id":event_id,"topic_id":"topic-launch","scope":"launch date","kind":kind,"text":text,
        "source_time":{"value":"2026-09-01","precision":"day","timezone":None},
        "effective_time":{"value":"2026-09-01","precision":"day","timezone":None},
        "learned_at":"2026-09-20T10:00:00Z","evidence":[evidence(record_id,span_id)],
        "prior_event_ids":prior_ids or [],"review_state":review,"human_review_state":human,
        "automated_reason":reason,"human_reviewed_by":None,"human_reviewed_at":None}


def state():
    old=event("old","commitment","Launch in October","old","old-span")
    proposed=event("proposal","replacement","October is replaced by November","new","new-span",
        ["old"],"pending","pending","The later signed note explicitly replaces October with November.")
    proposed["evidence"].append(evidence("old","old-span"))
    return {"corpus_generation":3,"privacy_generation":1,"overview":None,"answers":{"answer":{"valid":True}},
        "memories":{},"history":{"old":old,"proposal":proposed},
        "documents":{"document-old":{"id":"document-old","ai_status":"active","deleted":False},
                     "document-new":{"id":"document-new","ai_status":"active","deleted":False}},
        "records":{"old":record("old","October plan","old-span","The launch is agreed for October.","2026-09-01"),
                   "new":record("new","November replacement","new-span","October is replaced by November.","2026-09-10")}}


def platform(data):
    service=object.__new__(EvidencePlatform);service.secret=b"t"*32
    @asynccontextmanager
    async def transaction(self,ctx,**_kwargs):yield None,data
    service.transaction=MethodType(transaction,service)
    return service


@pytest.mark.asyncio
async def test_pending_stale_review_exposes_old_and_new_evidence():
    page=await platform(state()).list_stale_reviews(context(),PageRequest(limit=25))
    review=page.items[0]
    assert review.state=="pending"
    assert review.reason.startswith("The later signed note")
    assert review.stale_evidence[0].source_title=="October plan"
    assert review.stale_evidence[0].quote=="The launch is agreed for October."
    assert review.marking_evidence[0].source_title=="November replacement"


@pytest.mark.asyncio
async def test_approval_publishes_history_and_invalidates_saved_answers():
    data=state();service=platform(data)
    result=await service.decide_stale_review(context(),"proposal","approve")
    assert result.state=="approved" and result.reviewed_by=="admin-1"
    assert data["history"]["proposal"]["review_state"]=="passed"
    assert data["answers"]["answer"]["valid"] is False
    assert data["corpus_generation"]==4


@pytest.mark.asyncio
async def test_rejection_keeps_proposal_out_of_usable_history_and_is_final():
    data=state();service=platform(data)
    result=await service.decide_stale_review(context(),"proposal","reject")
    assert result.state=="rejected"
    assert data["history"]["proposal"]["review_state"]=="failed"
    with pytest.raises(DomainError) as error:
        await service.decide_stale_review(context(),"proposal","approve")
    assert error.value.code=="invalid_input"


@pytest.mark.asyncio
async def test_legacy_automated_stale_marking_fails_closed_until_human_approval():
    data=state();proposal=data["history"]["proposal"]
    proposal.update(review_state="passed",human_review_state="not_required",automated_reason=None)
    service=platform(data);query=HistoryQuery(topic_id="topic-launch",scope="launch date",as_of=None)
    before=await service.read_history(context(),query,PageRequest(limit=25))
    assert [item.id for item in before.items]==["old"]
    reviews=await service.list_stale_reviews(context(),PageRequest(limit=25))
    assert reviews.items[0].state=="pending" and "Confirm the source evidence" in reviews.items[0].reason
    await service.decide_stale_review(context(),"proposal","approve")
    after=await service.read_history(context(),query,PageRequest(limit=25))
    assert [item.id for item in after.items]==["old","proposal"]
