"""Explicit synthetic substitutes for independent UI development only."""
from datetime import datetime,timezone,timedelta
from app.contracts.models import *
from app.contracts.ports import Services
from app.contracts.errors import DomainError

class FixtureServices:
    def __init__(self):
        self.calls=[]
        self.revoked=False
        self.release_failure=None
    def services(self): return Services(self,self,self,self,self,self,self)
    async def login(self,email,password):
        if email!="fixture@synthetic.invalid" or password!="synthetic-password": raise DomainError("unauthenticated")
        return LoginResult(session_token="synthetic-session",me=await self.me(None))
    async def authenticate(self,token):
        if token!="synthetic-session" or self.revoked: raise DomainError("unauthenticated")
        return SessionPrincipal(user_id="fixture-user",session_id="fixture-session",expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
    async def me(self,principal):
        return Me(user_id="fixture-user",display_name="SYNTHETIC DEVELOPMENT FIXTURE",csrf_token="synthetic-csrf",expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
    async def validate_csrf(self,principal,token):
        if token!="synthetic-csrf": raise DomainError("csrf_failed")
    async def logout(self,principal): self.revoked=True
    async def authorize(self,principal,project_id,required_role="member"):
        if project_id!="fixture-project": raise DomainError("not_found")
        return RequestContext(user_id=principal.user_id,session_id=principal.session_id,project_id=project_id,role="admin",access_revision=1,corpus_generation=1,privacy_generation=0)
    async def list_projects(self,principal,page):
        return Page[Project](items=[Project(id="fixture-project",name="SYNTHETIC DEVELOPMENT FIXTURE",role="admin")],next_cursor=None)
    async def create_project(self,principal,name):
        return Project(id="created-project",name=name.strip(),role="admin")
    async def list_project_types(self,ctx,page=None):
        return Page[ProjectType](items=[ProjectType(name="report"),ProjectType(name="email")],next_cursor=None)
    async def create_project_type(self,ctx,name):return ProjectType(name=name)
    async def delete_project(self,ctx):
        self.calls.append("delete_project")
    async def list_documents(self,ctx,page): return Page[Document](items=[],next_cursor=None)
    async def list_members(self,ctx,page):
        return Page[Member](items=[Member(user_id="fixture-user",display_name="SYNTHETIC DEVELOPMENT FIXTURE",role="admin",granted_at=datetime.now(timezone.utc))],next_cursor=None)
    async def list_people(self,ctx,page):
        return Page[Person](items=[Person(id="PERSON_fixture",display_name="Fixture Person",kind="client",contacts=[Contact(kind="email",value="fixture-person@example.test")],state="active")],next_cursor=None)
    async def list_original_documents(self,ctx,page):
        return Page[OriginalDocument](items=[OriginalDocument(id="fixture-document",title="Fixture source",record_type="report",processed_filename="fixture.txt",processed_sources=[ProcessedDocumentSource(record_id="fixture-record",record_version=1,title="Fixture processed source",processed_content_url="/projects/fixture-project/sources/fixture-record?version=1&span=fixture-span")],created_at=datetime.now(timezone.utc),updated_at=datetime.now(timezone.utc))],next_cursor=None)
    async def get_original_document(self,ctx,document_id):
        if document_id!="fixture-document": raise DomainError("not_found")
        return OriginalDocumentContent(id=document_id,title="Fixture source",record_type="report",processed_filename="fixture.txt",processed_sources=[],processed_content="PERSON_fixture source.",created_at=datetime.now(timezone.utc),updated_at=datetime.now(timezone.utc))
    async def search_identity_mappings(self,ctx,query,page):
        item=IdentityMapping(pseudonym="PERSON_fixture",display_name="Fixture Person",kind="client",contacts=[Contact(kind="email",value="fixture-person@example.test")],state="active")
        return Page[IdentityMapping](items=[item] if not query or query.casefold() in (item.pseudonym+item.display_name+item.contacts[0].value).casefold() else [],next_cursor=None)
    async def get_status(self,ctx):
        return ProjectStatus(project_id=ctx.project_id,eligible_documents=0,eligible_records=0,operational_job_counts={},write_barrier=False,snapshot=Snapshot(corpus_generation=1,privacy_generation=0))
    async def get_overview(self,ctx):
        return Overview(state="pending",id=None,claims=[],receipts=[],coverage=None,snapshot=Snapshot(corpus_generation=1,privacy_generation=0),error_code=None)
    async def get_timeline(self,ctx,page):
        items=[]
        for index,record_type in enumerate(("email","transcript","report","specification"),1):
            items.append(TimelineRecord(project_id=ctx.project_id,record_id=f"fixture-record-{index}",original_doc_id="fixture-document",record_version=1,title=f"Fixture {record_type} record",record_type=record_type,source_time=SourceTime(value=f"2026-09-{index+10:02d}",precision="day",timezone=None),level1_summary="A short fixture description.",level2_summary="A fuller fixture summary.",processed_content_url=f"/projects/fixture-project/sources/fixture-record-{index}?version=1&span=fixture-span"))
        return Page[TimelineRecord](items=items,next_cursor=None)
    async def list_jobs(self,ctx,page): return Page[Job](items=[],next_cursor=None)
    def stale_review(self,state="pending"):
        def receipt(record_id,title,date,quote):
            ref=EvidenceRef(project_id="fixture-project",original_doc_id="fixture-document",record_id=record_id,record_version=1,span_ids=[record_id+"-span"])
            return Receipt(id="receipt-"+record_id,evidence_ref=ref,quote=quote,
                source_url=f"/projects/fixture-project/sources/{record_id}?version=1&span={record_id}-span",
                source_title=title,record_type="report",source_time=SourceTime(value=date,precision="day",timezone=None),
                source_locations=[SourceLocation(line_start=1,line_end=1,paragraph=None,message_ordinal=None,turn_ordinal=None,timestamp_label=None)])
        return StaleReview(id="stale-review",kind="replacement",scope="launch date",
            proposed_change="November replaces October.",reason="The later signed decision explicitly replaces the earlier date.",
            state=state,stale_evidence=[receipt("october-plan","October launch plan","2026-09-01","The launch is agreed for October.")],
            marking_evidence=[receipt("november-decision","November replacement","2026-09-10","Both parties replace October with November.")],created_at=datetime.now(timezone.utc),
            reviewed_by="fixture-user" if state!="pending" else None,
            reviewed_at=datetime.now(timezone.utc) if state!="pending" else None)
    async def list_stale_reviews(self,ctx,page):
        return Page[StaleReview](items=[self.stale_review()],next_cursor=None)
    async def decide_stale_review(self,ctx,event_id,decision):
        self.calls.append(("stale_review",event_id,decision))
        return self.stale_review("approved" if decision=="approve" else "rejected")
    async def begin_chat(self,ctx,input):
        self.calls.append("begin")
        deadline=datetime.now(timezone.utc)+timedelta(seconds=60)
        return BeginChatReady(attempt=ChatAttempt(attempt_id="attempt",request_id=input.request_id,conversation_id=input.conversation_id,input_hash="0"*64,lease_token="internal-secret",deadline=deadline),
          input=AnswerInput(question=NormalizedText(text="normalized",person_ids=[],ambiguous=False),history=[],request_id=input.request_id,conversation_id=input.conversation_id,deadline=deadline))
    async def answer(self,ctx,input):
        self.calls.append("answer")
        assert input.question.text=="normalized"
        return ReviewedCandidate(claims=[],receipts=[],dependencies=[],coverage=Coverage(state="insufficient",records=[],limitations=[]),
          cannot_establish="no_evidence",snapshot=Snapshot(corpus_generation=1,privacy_generation=0),review_results=[],candidate_digest="0"*64,omission_proof=None)
    async def release_answer(self,ctx,attempt,candidate):
        self.calls.append("release")
        if self.release_failure: raise DomainError(self.release_failure)
        return Answer(id="fixture-answer",conversation_id=attempt.conversation_id,request_id=attempt.request_id,claims=[],receipts=[],coverage=candidate.coverage,cannot_establish=candidate.cannot_establish,snapshot=candidate.snapshot,created_at=datetime.now(timezone.utc))
    async def fail_chat(self,ctx,attempt,code): self.calls.append("fail")

def fixture_app():
    from app.main import create_app
    from app.config import HttpSettings
    import os
    return create_app(FixtureServices().services(),HttpSettings(trusted_origins=(os.environ.get("RELEX_FIXTURE_ORIGIN","http://127.0.0.1:18080"),),secure_cookie=False,allow_loopback_http=True))
