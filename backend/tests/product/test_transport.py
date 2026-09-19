"""Development-only route checks. These never establish live product acceptance."""
import httpx
import pytest
from .fixtures import FixtureServices
from app.main import create_app
from app.config import HttpSettings

@pytest.mark.asyncio
async def test_real_route_orders_begin_answer_release_and_withholds_on_failure():
    fixture=FixtureServices()
    app=create_app(fixture.services(),HttpSettings(secure_cookie=False,allow_loopback_http=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://127.0.0.1:18080") as client:
        headers={"Origin":"http://127.0.0.1:18080"}
        login=await client.post("/api/login",json={"email":"fixture@synthetic.invalid","password":"synthetic-password"},headers=headers)
        assert login.status_code==200 and "session_token" not in login.json()
        headers["X-CSRF-Token"]=login.json()["csrf_token"]
        payload={"question":"raw","conversation_id":"conversation","request_id":"request"}
        reply=await client.post("/api/projects/fixture-project/chat",json=payload,headers=headers)
        assert reply.status_code==200 and fixture.calls==["begin","answer","release"]
        assert "candidate_digest" not in reply.json()
        fixture.release_failure="evidence_changed"
        reply=await client.post("/api/projects/fixture-project/chat",json={**payload,"request_id":"second"},headers=headers)
        assert reply.status_code==409 and set(reply.json())=={"error"}
        assert fixture.calls[-4:]==["begin","answer","release","fail"]
        wrong=await client.post("/api/projects/fixture-project/chat",json={**payload,"history":[]},headers=headers)
        assert wrong.status_code==422
        denied=await client.post("/api/projects/fixture-project/chat",json=payload)
        assert denied.status_code==403
        assert (await client.get("/api/projects/fixture-project/documents?unknown=1")).status_code==422
        assert (await client.get("/api/projects/another-project/documents")).status_code==404


@pytest.mark.asyncio
async def test_timeline_route_is_project_authorized():
    fixture=FixtureServices()
    app=create_app(fixture.services(),HttpSettings(secure_cookie=False,allow_loopback_http=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://127.0.0.1:18080") as client:
        headers={"Origin":"http://127.0.0.1:18080"}
        login=await client.post("/api/login",json={"email":"fixture@synthetic.invalid","password":"synthetic-password"},headers=headers)
        assert login.status_code==200

        timeline=await client.get("/api/projects/fixture-project/timeline")

        assert timeline.status_code==200
        assert timeline.json()["items"][0]["level2_summary"]=="A fuller fixture summary."
        assert (await client.get("/api/projects/another-project/timeline")).status_code==404
