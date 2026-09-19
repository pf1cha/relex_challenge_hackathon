"""Canonical project services with PostgreSQL-serialized authorization and release.

A project row is locked only during local validation/persistence. Provider/index
calls occur in the runner outside transactions. Each persisted object is validated
with contract DTOs before it can be returned to another slice.
"""
from __future__ import annotations
import base64, hashlib, hmac, json, secrets, uuid, re
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta, date
from urllib.parse import quote
from psycopg.types.json import Jsonb
from ..contracts.models import *
from ..contracts.errors import DomainError
from ..contracts.hashing import compact, candidate_digest, make_entry_id, artifact_key
from .privacy import normalize, person_occurs
from .parsing import parse

def now(): return datetime.now(timezone.utc)
def iso(): return now().isoformat()
def uid(): return str(uuid.uuid4())
def dump(value): return value.model_dump(mode="json") if hasattr(value,"model_dump") else value
def timeline_order(item):
    source_time=item.source_time
    if source_time.value is None:return (1,0,0,item.record_id)
    try:
        if source_time.precision=="instant":
            parsed=datetime.fromisoformat(source_time.value.replace("Z","+00:00"))
            if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone.utc)
        elif source_time.precision=="day":parsed=datetime.fromisoformat(source_time.value).replace(tzinfo=timezone.utc)
        elif source_time.precision=="month":parsed=datetime.fromisoformat(source_time.value+"-01").replace(tzinfo=timezone.utc)
        elif source_time.precision=="year":parsed=datetime(int(source_time.value),1,1,tzinfo=timezone.utc)
        else:return (1,0,0,item.record_id)
        return (0,0,parsed.timestamp(),item.record_id)
    except (TypeError,ValueError,OverflowError):
        return (0,1,source_time.value,item.record_id)
def require(condition, code="contract_violation"):
    if not condition: raise DomainError(code)
def password_hash(password, salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+":"+hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def fresh_state():
    return dict(corpus_generation=0,privacy_generation=0,lifecycle_revision=0,reservation=0,write_barrier=False,members={},project_types={x: True for x in ("email", "transcript", "report", "specification")},documents={},records={},people={},jobs={},memories={},chunks={},entries={},history={},checkpoints={},operations={},conversations={},messages={},attempts={},answers={},plans={},capabilities={},overview=None,privacy_plans={},privacy_diagnostics={},privacy_resolutions={},access_epochs={})

class EvidencePlatform:
    def __init__(self, db, secret, privacy_detector=None, upload_limit_bytes=10*1024*1024, request_deadline_seconds=120, lease_seconds=300):
        require(len(secret)>=32,"invalid_input")
        self.db=db;self.secret=secret.encode() if isinstance(secret,str) else secret
        self.privacy_detector=privacy_detector;self.upload_limit_bytes=upload_limit_bytes
        self.request_deadline_seconds=request_deadline_seconds;self.lease_seconds=lease_seconds
        self.auth=self.projects=self.documents=self.sources=self.administration=self.conversations=self
        from .relational import load_project, sync_project
        self.load_relational_project = load_project
        self.sync_relational = sync_project
        self.reader=Reader(self);self.retrieval=self;self.artifacts=self
        from .jobs import Jobs, Ledger
        self.jobs=Jobs(self);self.ledger=Ledger(self)

    def keyed(self,text):return hmac.new(self.secret,text.encode(),hashlib.sha256).hexdigest()

    async def bootstrap_user(self,email,password,display_name):
        require(1<=len(email)<=320 and len(password)>=10 and 1<=len(display_name)<=255,"invalid_input")
        async with self.db.connection() as c:
            existing=await (await c.execute("SELECT id FROM users WHERE email=%s",(email.casefold(),))).fetchone()
            if existing:return existing["id"]
            user_id=uid()
            await c.execute("INSERT INTO users(id,email,display_name,password_hash) VALUES(%s,%s,%s,%s)",(user_id,email.casefold(),display_name,password_hash(password)))
            return user_id

    async def register(self, email, password, display_name):
        email=email.strip().casefold(); display_name=display_name.strip()
        require(len(email)<=320 and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email)
                and 10<=len(password)<=4096 and 1<=len(display_name)<=255,"invalid_input")
        async with self.db.connection() as c:
            row=await (await c.execute(
                "INSERT INTO users(id,email,display_name,password_hash) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT(email) DO NOTHING RETURNING id",
                (uid(),email,display_name,password_hash(password)))).fetchone()
            require(row,"email_registered")
        return await self.login(email,password)

    async def bootstrap_project(self,name,admin_id,project_id=None):
        project_id=project_id or uid();s=fresh_state()
        s["members"][admin_id]=dict(role="admin",revision=1,granted_at=iso())
        async with self.db.connection(restricted=True) as c:
            require(await (await c.execute("SELECT id FROM users WHERE id=%s",(admin_id,))).fetchone(),"not_found")
            await c.execute("INSERT INTO projects(id,name,data) VALUES(%s,%s,%s) ON CONFLICT(id) DO NOTHING",(project_id,name,Jsonb(s)))
            await self.sync_relational(c,project_id,s,restricted=True)
        return project_id

    async def _session(self,c,principal):
        row=await (await c.execute("SELECT s.*,u.display_name FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id=%s AND s.user_id=%s AND NOT s.revoked AND s.expires_at>now() AND u.active FOR SHARE OF s,u",(principal.session_id,principal.user_id))).fetchone()
        require(row,"unauthenticated");return row

    async def login(self,email,password):
        async with self.db.connection() as c:
            user=await (await c.execute("SELECT * FROM users WHERE email=%s AND active",(email.casefold(),))).fetchone()
            expected=user["password_hash"] if user else password_hash("dummy-password")
            require(user and hmac.compare_digest(password_hash(password,expected.split(":")[0]),expected),"unauthenticated")
            token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);sid=uid();expires=now()+timedelta(hours=12)
            await c.execute("INSERT INTO sessions(id,user_id,token_hash,csrf_hash,csrf_token,expires_at) VALUES(%s,%s,%s,%s,%s,%s)",(sid,user["id"],self.keyed(token),self.keyed(csrf),csrf,expires))
            return LoginResult(session_token=token,me=Me(user_id=user["id"],display_name=user["display_name"],csrf_token=csrf,expires_at=expires))

    async def authenticate(self,session_token):
        async with self.db.connection() as c:
            row=await (await c.execute("SELECT s.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=%s AND NOT revoked AND expires_at>now() AND u.active",(self.keyed(session_token),))).fetchone()
            require(row,"unauthenticated");return SessionPrincipal(user_id=row["user_id"],session_id=row["id"],expires_at=row["expires_at"])

    async def me(self,principal):
        async with self.db.connection() as c:
            r=await self._session(c,principal)
            return Me(user_id=principal.user_id,display_name=r["display_name"],csrf_token=r["csrf_token"],expires_at=r["expires_at"])

    async def validate_csrf(self,principal,token):
        async with self.db.connection() as c:
            r=await self._session(c,principal);require(hmac.compare_digest(r["csrf_hash"],self.keyed(token)),"csrf_failed")

    async def logout(self,principal):
        async with self.db.connection() as c:
            await c.execute("UPDATE sessions SET revoked=true,csrf_token='' WHERE id=%s AND user_id=%s",(principal.session_id,principal.user_id))

    def snapshot(self,s):return Snapshot(corpus_generation=s["corpus_generation"],privacy_generation=s["privacy_generation"])

    async def authorize(self,principal,project_id,required_role="member"):
        async with self.db.connection() as c:
            await self._session(c,principal)
            membership=await (await c.execute("SELECT role,access_revision FROM project_memberships WHERE project_id=%s AND user_id=%s",(project_id,principal.user_id))).fetchone()
            require(membership,"not_found")
            require(required_role!="admin" or membership["role"]=="admin","forbidden")
            state=await self.load_relational_project(c,project_id)
            require(state,"not_found")
            return RequestContext(user_id=principal.user_id,session_id=principal.session_id,project_id=project_id,role=membership["role"],access_revision=membership["access_revision"],**dump(self.snapshot(state)))

    @asynccontextmanager
    async def transaction(self,ctx,admin=False,write=False,fresh=False,restricted=False):
        async with self.db.connection(restricted=restricted) as c:
            if isinstance(ctx,RequestContext):
                await self._session(c,SessionPrincipal(user_id=ctx.user_id,session_id=ctx.session_id,expires_at=now()))
            s=await self.load_relational_project(c,ctx.project_id,restricted=restricted,for_update=True)
            require(s,"not_found")
            if isinstance(ctx,RequestContext):
                m=s["members"].get(ctx.user_id);require(m,"not_found")
                normalized=await (await c.execute("SELECT role,access_revision FROM project_memberships WHERE project_id=%s AND user_id=%s",(ctx.project_id,ctx.user_id))).fetchone()
                if normalized:
                    m={"role":normalized["role"],"revision":normalized["access_revision"]}
                require(not admin or m["role"]=="admin","forbidden")
                require(m["revision"]==ctx.access_revision and m["role"]==ctx.role,"evidence_changed")
            else:
                stored=s["capabilities"].get(ctx.capability_id);require(stored,"capability_denied")
                self._cap(s,JobCapability.model_validate(stored))
                require(ctx.snapshot==self.snapshot(s),"evidence_changed")
            if fresh and isinstance(ctx,RequestContext):require(self.snapshot(s)==Snapshot(corpus_generation=ctx.corpus_generation,privacy_generation=ctx.privacy_generation),"evidence_changed")
            if write: require(not s["write_barrier"],"write_barrier")
            yield c,s
            await self.sync_relational(c,ctx.project_id,s,restricted=restricted)

    def _cursor(self,binding,offset):
        raw=compact([binding,offset]);return base64.urlsafe_b64encode(raw.encode()).decode()+"."+self.keyed(raw)
    def _offset(self,cursor,binding):
        if not cursor:return 0
        try:
            raw,sig=cursor.rsplit(".",1);raw=base64.urlsafe_b64decode(raw).decode();data=json.loads(raw)
            require(hmac.compare_digest(sig,self.keyed(raw)) and data[0]==binding and type(data[1])==int and data[1]>=0,"stale_cursor")
            return data[1]
        except DomainError:raise
        except Exception:raise DomainError("stale_cursor") from None
    def _binding(self,ctx,s,operation,args=None):
        return [operation,ctx.project_id,getattr(ctx,"user_id",getattr(ctx,"job_id","")),getattr(ctx,"role","worker"),getattr(ctx,"access_revision",0),dump(self.snapshot(s)),args]
    def _page(self,items,page,binding):
        offset=self._offset(page.cursor,binding);chunk=items[offset:offset+page.limit]
        return Page(items=chunk,next_cursor=self._cursor(binding,offset+page.limit) if offset+page.limit<len(items) else None)

    async def list_projects(self,principal,page):
        async with self.db.connection() as c:
            await self._session(c,principal)
            rows=await (await c.execute(
                "SELECT p.id,p.name,m.role,m.access_revision FROM projects p "
                "JOIN project_memberships m ON m.project_id=p.id WHERE m.user_id=%s ORDER BY p.created_at,p.id",
                (principal.user_id,))).fetchall()
            items=[Project(id=r["id"],name=r["name"],role=r["role"]) for r in rows]
            return self._page(items,page,["projects",principal.user_id,[[r["id"],r["access_revision"]] for r in rows]])

    async def list_project_types(self,ctx):
        async with self.transaction(ctx) as (_,s):
            items=[ProjectType(name=name) for name in sorted(s.get("project_types", {}))]
            return Page(items=items,next_cursor=None)

    async def create_project_type(self,ctx,name):
        name=name.strip().casefold()
        require(re.fullmatch(r"[a-z0-9][a-z0-9 _-]{0,63}",name),"invalid_input")
        async with self.transaction(ctx,admin=True,write=True) as (_,s):
            require(name not in s.setdefault("project_types", {}),"already_exists")
            s["project_types"][name]=True
            return ProjectType(name=name)

    def _document(self,s,document_id):
        d=s["documents"].get(document_id);require(d and not d.get("deleted"),"not_found");return d
    def _record(self,s,record_id,preview=False):
        r=s["records"].get(record_id);require(r,"not_found")
        d=self._document(s,r["original_doc_id"])
        require(r["published"] and not r.get("quarantined") and (d["ai_status"]=="active" or preview),"source_unavailable")
        return r
    def _summary(self,r):
        return RecordSummary(record_id=r["record_id"],original_doc_id=r["original_doc_id"],record_version=r["record_version"],title=r["title"],record_type=r["record_type"],source_time=r["source_time"],total_chunks=len(r["chunk_ids"]))
    def _public_document(self,s,d,admin):
        count=sum(1 for r in s["records"].values() if r["original_doc_id"]==d["id"] and r["published"] and not r.get("quarantined") and (admin or d["ai_status"]=="active"))
        return Document(**{k:d[k] for k in Document.model_fields if k not in ("record_count",)},record_count=count)

    async def list_documents(self,ctx,page):
        async with self.transaction(ctx) as (_,s):
            admin=ctx.role=="admin"
            items=[self._public_document(s,d,admin) for d in s["documents"].values() if not d.get("deleted") and (admin or d["ai_status"]=="active" and d["processing_state"]=="completed")]
            return self._page(sorted(items,key=lambda x:(x.created_at,x.id)),page,self._binding(ctx,s,"documents"))
    async def list_records(self,ctx,document_id,page):
        async with self.transaction(ctx) as (_,s):
            d=self._document(s,document_id)
            require(ctx.role=="admin" or d["ai_status"]=="active","source_unavailable")
            items=[self._summary(r) for r in sorted(s["records"].values(),key=lambda r:(r.get("created_at",""),r["record_id"])) if r["original_doc_id"]==document_id and r["published"] and not r.get("quarantined")]
            return self._page(items,page,self._binding(ctx,s,"records",document_id))

    def _new_job(self,s,project_id,kind,docs=None,people=None,refs=None,plans=None,removals=None):
        t=iso();job=Job(id=uid(),project_id=project_id,kind=kind,state="pending",stage="received" if kind in ("ingest","activate","rebuild_aggregate") else "inventory" if kind=="reconcile" else "invalidating",counts={},error_code=None,retryable=False,created_at=t,updated_at=t)
        s["reservation"]+=1
        s["jobs"][job.id]=dict(public=dump(job),work=dump(WorkPlan(document_ids=docs or [],person_ids=people or [],record_versions=refs or [],rebuild_plan_ids=plans or [],removal_entry_ids=removals or [])),lease_token=None,expires_at=None,lifecycle_revision=s["lifecycle_revision"],publication_generation=s["reservation"],results=[])
        return job

    def _invalidate(self,s,privacy=False,lifecycle=False):
        s["corpus_generation"]+=1
        if privacy:s["privacy_generation"]+=1
        if lifecycle:s["lifecycle_revision"]+=1
        s["overview"]=None
        for a in s["answers"].values():a["valid"]=False
        for m in s["memories"].values():
            if m["data"]["kind"]=="overview":m["valid"]=False
            elif m["data"]["kind"]=="topic":
                try:
                    for dep in m["data"]["dependencies"]:self._dependency(s,Dependency.model_validate(dep))
                except DomainError:m["valid"]=False
    async def submit_upload(self,ctx,upload):
        require(1<=len(upload.filename)<=255,"invalid_input")
        require(len(upload.content)<=self.upload_limit_bytes,"upload_too_large")
        require(not upload.content.startswith((b"%PDF-",b"PK\x03\x04")) and not upload.filename.lower().endswith((".pdf",".doc",".docx",".png",".jpg",".jpeg",".zip")),"unsupported_format")
        try:text=upload.content.decode("utf-8")
        except UnicodeDecodeError:raise DomainError("unsupported_format") from None
        require(text.strip() and "\x00" not in text,"unsupported_format")
        async with self.transaction(ctx,admin=True,write=True,restricted=True) as (_,s):
            require(upload.record_type in s.get("project_types", {}),"invalid_input")
            doc_id=uid();title=normalize(upload.filename,s["people"]).text
            if normalize(upload.filename,s["people"]).ambiguous:title="Restricted upload"
            job=self._new_job(s,ctx.project_id,"ingest",docs=[doc_id])
            s["documents"][doc_id]=dict(id=doc_id,project_id=ctx.project_id,title=title,record_type=upload.record_type,ai_status="active",processing_state="pending",records_url=f"/api/projects/{quote(ctx.project_id,safe='')}/documents/{doc_id}/records",latest_job_id=job.id,created_at=iso(),updated_at=iso(),raw=text,raw_filename=upload.filename,deleted=False)
            return job

    async def get_status(self,ctx):
        async with self.transaction(ctx) as (_,s):
            records=[r for r in s["records"].values() if r["published"] and not r.get("quarantined") and s["documents"][r["original_doc_id"]]["ai_status"]=="active" and not s["documents"][r["original_doc_id"]].get("deleted")]
            counts={k:sum(j["public"]["state"]==k for j in s["jobs"].values()) for k in ("pending","running","failed","completed")}
            return ProjectStatus(project_id=ctx.project_id,eligible_documents=len({r["original_doc_id"] for r in records}),eligible_records=len(records),operational_job_counts=counts if ctx.role=="admin" else None,write_barrier=s["write_barrier"],snapshot=self.snapshot(s))
    async def get_overview(self,ctx):
        async with self.transaction(ctx) as (_,s):
            if s["overview"]:
                candidate=ReviewedCandidate.model_validate(s["overview"]["candidate"])
                try:self._validate_candidate(s,ctx.project_id,candidate)
                except DomainError:pass
                else:return Overview(state="ready",id=s["overview"]["id"],claims=candidate.claims,receipts=candidate.receipts,coverage=candidate.coverage,snapshot=self.snapshot(s),error_code=None)
            return Overview(state="pending",id=None,claims=[],receipts=[],coverage=None,snapshot=self.snapshot(s),error_code=None)
    async def get_timeline(self,ctx,page):
        async with self.transaction(ctx) as (_,s):
            summaries={}
            valid_memories=(stored.get("data",{}) for stored in s["memories"].values() if stored.get("valid"))
            for memory in sorted(valid_memories,key=lambda value:(value.get("updated_at",""),value.get("id",""))):
                if memory.get("project_id")!=ctx.project_id or memory.get("kind")!="record" or memory.get("level") not in (1,2):continue
                for dependency in memory.get("dependencies",[]):
                    key=(dependency.get("record_id"),dependency.get("record_version"))
                    summaries.setdefault(key,{})[memory["level"]]={"text":memory.get("text"),"span_ids":dependency.get("span_ids",[])}
            items=[]
            for r in s["records"].values():
                document=s["documents"].get(r["original_doc_id"])
                if not document or document.get("deleted") or document.get("ai_status")!="active":continue
                if not r.get("published") or r.get("quarantined"):continue
                record_summaries=summaries.get((r["record_id"],r["record_version"]),{})
                valid_span_ids={span["span_id"] for span in r.get("spans",[])}
                summary_span_ids=next((summary["span_ids"] for level in (2,1) if (summary:=record_summaries.get(level)) and summary["span_ids"]),[])
                linked_span_id=next((span_id for span_id in summary_span_ids if span_id in valid_span_ids),None)
                first_span=next((span for span in r.get("spans",[]) if span["span_id"]==linked_span_id),next(iter(r.get("spans",[])),None))
                source_url=None if first_span is None else f"/projects/{quote(ctx.project_id,safe='')}/sources/{quote(r['record_id'],safe='')}?version={r['record_version']}&span={quote(first_span['span_id'],safe='')}"
                items.append(TimelineRecord(project_id=ctx.project_id,record_id=r["record_id"],original_doc_id=r["original_doc_id"],record_version=r["record_version"],title=r["title"],record_type=r["record_type"],source_time=r["source_time"],level1_summary=record_summaries.get(1,{}).get("text"),level2_summary=record_summaries.get(2,{}).get("text"),processed_content_url=source_url))
            items.sort(key=timeline_order)
            return self._page(items,page,self._binding(ctx,s,"timeline"))
    async def get_filters(self,ctx):
        async with self.transaction(ctx) as (_,s):
            rs=[]
            for r in s["records"].values():
                try:self._record(s,r["record_id"]);rs.append(r)
                except DomainError:continue
            docids={r["original_doc_id"] for r in rs};pids={x for r in rs for x in r["person_ids"]}
            topics={t for r in rs for eid in r["entry_ids"] for t in s["entries"].get(eid,{}).get("topic_ids",[])}
            return FilterOptions(record_types=sorted({r["record_type"] for r in rs}),documents=[Option(id=x,label=s["documents"][x]["title"]) for x in sorted(docids)],topics=[Option(id=x,label=x) for x in sorted(topics)],people=[Option(id=x,label=x) for x in sorted(pids)])

    def _record_page(self,s,ctx,r,page):
        chunks=[s["chunks"][x] for x in r["chunk_ids"]]
        binding=self._binding(ctx,s,"read_record",[r["record_id"],r["record_version"]])
        offset=self._offset(page.cursor,binding);selected=chunks[offset:offset+page.limit]
        ids={sl["span_id"] for chunk in selected for sl in chunk["slices"]}
        return RecordPage(record=self._summary(r),spans=[Span.model_validate(x) for x in r["spans"] if x["span_id"] in ids],returned_chunk_ids=[x["id"] for x in selected],total_chunks=len(chunks),next_cursor=self._cursor(binding,offset+page.limit) if offset+page.limit<len(chunks) else None,complete=offset+page.limit>=len(chunks),snapshot=self.snapshot(s))

    async def read_record(self,ctx,record_id,page):
        async with self.transaction(ctx,fresh=True) as (_,s):
            return self._record_page(s,ctx,self._record(s,record_id),page)

    def _source_page(self,s,ctx,r,span_id,limit=25,cursor=None):
        require(1<=limit<=100,"invalid_input")
        indices=[i for i,x in enumerate(r["spans"]) if x["span_id"]==span_id];require(indices,"source_unavailable")
        binding=self._binding(ctx,s,"source",[r["record_id"],r["record_version"],span_id,limit])
        start=self._offset(cursor,binding) if cursor else max(0,indices[0]-limit//2)
        end=min(len(r["spans"]),start+limit)
        return SourcePage(record=self._summary(r),spans=r["spans"][start:end],highlighted_span_ids=[span_id],next_cursor=self._cursor(binding,end) if end<len(r["spans"]) else None,previous_cursor=self._cursor(binding,max(0,start-limit)) if start else None,snapshot=self.snapshot(s))
    async def read_source(self,ctx,request):
        async with self.transaction(ctx,fresh=True) as (_,s):
            r=self._record(s,request.record_id,preview=ctx.role=="admin")
            require(r["record_version"]==request.version,"source_unavailable")
            return self._source_page(s,ctx,r,request.span_id,request.limit or 25,request.cursor)

    def _receipt(self,s,project_id,ref):
        require(ref.project_id==project_id,"not_found");r=self._record(s,ref.record_id)
        require(ref.record_version==r["record_version"] and ref.original_doc_id==r["original_doc_id"],"source_unavailable")
        require(bool(ref.span_ids) and len(set(ref.span_ids))==len(ref.span_ids))
        spans={x["span_id"]:x for x in r["spans"]}
        require(all(x in spans for x in ref.span_ids),"source_unavailable")
        picked=[spans[x] for x in ref.span_ids];ordinals=[x["ordinal"] for x in picked]
        require(ordinals==list(range(ordinals[0],ordinals[0]+len(ordinals))))
        return Receipt(id="receipt_"+hashlib.sha256(compact(dump(ref)).encode()).hexdigest()[:32],evidence_ref=ref,quote="\n".join(x["text"] for x in picked),source_url=f"/projects/{quote(project_id,safe='')}/sources/{quote(ref.record_id,safe='')}?version={ref.record_version}&span={quote(ref.span_ids[0],safe='')}",source_title=r["title"],record_type=r["record_type"],source_time=r["source_time"],source_locations=[x["source_location"] for x in picked])

    async def list_members(self,ctx,page):
        async with self.transaction(ctx,admin=True) as (c,s):
            items=[]
            for user_id,m in s["members"].items():
                u=await (await c.execute("SELECT display_name FROM users WHERE id=%s",(user_id,))).fetchone()
                items.append(Member(user_id=user_id,display_name=u["display_name"],role=m["role"],granted_at=m["granted_at"]))
            return self._page(sorted(items,key=lambda x:(x.granted_at,x.user_id)),page,self._binding(ctx,s,"members"))
    async def set_member_by_email(self,ctx,email,role):
        # Require project administration before looking up a registered account.
        async with self.transaction(ctx,admin=True) as (c,s):
            u=await (await c.execute("SELECT id FROM users WHERE email=%s AND active",
                                    (email.strip().casefold(),))).fetchone()
            require(u,"not_found")
            user_id=u["id"]
        return await self.set_member(ctx,user_id,role)

    async def set_member(self,ctx,user_id,role):
        require(role in ("admin","member"),"invalid_input")
        async with self.transaction(ctx,admin=True) as (c,s):
            u=await (await c.execute("SELECT display_name FROM users WHERE id=%s AND active",(user_id,))).fetchone();require(u,"not_found")
            old=s["members"].get(user_id)
            if old and old["role"]=="admin" and role!="admin":require(sum(m["role"]=="admin" for m in s["members"].values())>1,"last_admin")
            revision=max((old or {}).get("revision",0),s.get("access_epochs",{}).get(user_id,0))+1
            s["members"][user_id]=dict(role=role,revision=revision,granted_at=iso())
            return Member(user_id=user_id,display_name=u["display_name"],role=role,granted_at=s["members"][user_id]["granted_at"])
    async def remove_member(self,ctx,user_id):
        async with self.transaction(ctx,admin=True) as (_,s):
            old=s["members"].get(user_id);require(old,"not_found")
            require(old["role"]!="admin" or sum(m["role"]=="admin" for m in s["members"].values())>1,"last_admin")
            # Preserve monotonically advancing access epoch even after regrant.
            s.setdefault("access_epochs",{})[user_id]=old["revision"]+1
            del s["members"][user_id]
    async def list_people(self,ctx,page):
        async with self.transaction(ctx,admin=True,restricted=True) as (_,s):
            items=[Person.model_validate(p) for p in s["people"].values()]
            return self._page(items,page,self._binding(ctx,s,"people"))
    async def associate_person(self,ctx,input):
        require(1<=len(input.display_name)<=255 and all(1<=len(c.value)<=500 for c in input.contacts),"invalid_input")
        async with self.transaction(ctx,admin=True,write=True,restricted=True) as (_,s):
            if input.person_id:require(input.person_id in s["people"],"not_found")
            person_id=input.person_id or "PERSON_"+secrets.token_hex(8)
            for pid,p in s["people"].items():
                if pid!=person_id:require(not {c.value.casefold() for c in input.contacts}&{c["value"].casefold() for c in p["contacts"]},"ambiguous_person")
            p=Person(id=person_id,display_name=input.display_name,kind=input.kind,contacts=input.contacts,state="active")
            s["people"][person_id]=dump(p)
            if input.person_id:
                s["privacy_plans"]={}
                for record in s["records"].values():
                    record["quarantined"]=True
                self._invalidate(s,privacy=True)
            return p

    def _active_lifecycle(self,s,kind,target):
        for job in s["jobs"].values():
            if target in job["work"]["document_ids"]+job["work"]["person_ids"] and job["public"]["state"] in ("pending","running","failed"):
                if job["public"]["kind"]==kind:return Job.model_validate(job["public"])
                if job["public"]["kind"]!="ingest":raise DomainError("write_barrier")
        return None
    async def mutate_document(self,ctx,document_id,action):
        require(action in ("activate","deactivate","delete"),"invalid_input")
        async with self.transaction(ctx,admin=True,restricted=True) as (_,s):
            kind="delete_document" if action=="delete" else action
            existing=self._active_lifecycle(s,kind,document_id)
            if existing:return existing
            d=self._document(s,document_id)
            require(not s["write_barrier"],"write_barrier")
            if action=="activate":d["ai_status"]="active"
            else:d["ai_status"]="inactive"
            self._invalidate(s,lifecycle=True)
            affected=[r for r in s["records"].values() if r["original_doc_id"]==document_id]
            removals=[e for r in affected for e in r["entry_ids"]]
            if action in ("activate","delete"):
                for r in affected:r["published"]=False
            if action=="delete":s["write_barrier"]=True;d["deleted"]=True
            refs=[RecordVersionRef(record_id=r["record_id"],record_version=r["record_version"]) for r in affected] if action=="activate" else []
            job=self._new_job(s,ctx.project_id,kind,docs=[document_id],refs=refs,removals=removals)
            d.update(latest_job_id=job.id,processing_state="pending",updated_at=iso())
            return job

    async def erase_person(self,ctx,person_id):
        async with self.transaction(ctx,admin=True,restricted=True) as (_,s):
            require(person_id in s["people"],"not_found")
            existing=self._active_lifecycle(s,"erase_person",person_id)
            if existing:return existing
            require(not s["write_barrier"],"write_barrier")
            s["write_barrier"]=True;s["people"][person_id]["state"]="erasing";self._invalidate(s,privacy=True,lifecycle=True)
            affected=[r for r in s["records"].values() if person_occurs(r,person_id,s["people"])]
            for r in affected:r["quarantined"]=True
            job=self._new_job(s,ctx.project_id,"erase_person",docs=sorted({r["original_doc_id"] for r in affected}),people=[person_id],removals=[e for r in affected for e in r["entry_ids"]])
            return job

    @staticmethod
    def _recoverable_cleanup(j):
        # Reclassify legacy provider-shape failures without replacing inventory.
        # Retry still performs every validation and never releases the barrier early.
        p=j["public"]
        if p["state"]=="failed" and p["kind"] in ("erase_person","delete_document") and p["stage"]=="rebuilding" and p["error_code"]=="contract_violation":
            p["retryable"]=True

    async def list_jobs(self,ctx,page):
        async with self.transaction(ctx,admin=True) as (_,s):
            items=[]
            for job in s["jobs"].values():
                view={"public":dict(job["public"])}
                self._recoverable_cleanup(view)
                items.append(Job.model_validate(view["public"]))
            items=sorted(items,key=lambda x:(x.created_at,x.id))
            return self._page(items,page,self._binding(ctx,s,"jobs"))
    async def get_job(self,ctx,job_id):
        async with self.transaction(ctx,admin=True) as (_,s):
            require(job_id in s["jobs"],"not_found")
            view={"public":dict(s["jobs"][job_id]["public"])}
            self._recoverable_cleanup(view)
            return Job.model_validate(view["public"])
    async def list_privacy_diagnostics(self,ctx,page):
        async with self.transaction(ctx,admin=True,restricted=True) as (_,s):
            items=[PrivacyDiagnostic.model_validate(x) for x in s.get("privacy_diagnostics",{}).values()]
            return self._page(sorted(items,key=lambda x:(x.state,x.updated_at,x.id)),page,self._binding(ctx,s,"privacy-diagnostics"))

    async def resolve_privacy_diagnostic(self,ctx,diagnostic_id,resolution):
        require(1<=len(resolution)<=500,"invalid_input")
        async with self.transaction(ctx,admin=True,write=True,restricted=True) as (_,s):
            raw=s.get("privacy_diagnostics",{}).get(diagnostic_id);require(raw,"not_found")
            require(raw["state"]=="open","invalid_input")
            record=s["records"].get(raw["record_id"]);require(record and record["record_version"]==raw["record_version"],"evidence_changed")
            allowed={"organization","role","system_code","contact","personal_identifier","private_cause"}
            if resolution.startswith("bind:"):
                require(resolution[5:] in s["people"] and raw["kind"] in ("person","uncertain"),"invalid_input")
            else:require(resolution in allowed,"invalid_input")
            compatible={
                "organization":{"person","organization","uncertain"},
                "role":{"person","role","uncertain"},
                "system_code":{"personal_identifier","uncertain"},
                "contact":{"contact","uncertain"},
                "personal_identifier":{"personal_identifier","uncertain"},
                "private_cause":{"contextual_circumstance","uncertain"},
            }
            if not resolution.startswith("bind:"):require(raw["kind"] in compatible[resolution],"invalid_input")
            require(type(raw.get("start")) is int and type(raw.get("end")) is int,"invalid_input")
            if raw["span_id"].startswith("title:"):
                source=s["documents"][record["original_doc_id"]]["raw_filename"]
            else:
                source=next((span["text"] for span in record["raw_spans"] if span["span_id"]==raw["span_id"]),None)
            require(source is not None and 0<=raw["start"]<raw["end"]<=len(source),"evidence_changed")
            expected_text=source[raw["start"]:raw["end"]]
            resolution_id=uid()
            s.setdefault("privacy_resolutions",{})[resolution_id]={
                "id":resolution_id,"diagnostic_id":diagnostic_id,"admin_user_id":ctx.user_id,
                "record_id":raw["record_id"],"record_version":raw["record_version"],
                "source_hash":record["source_hash"],"span_id":raw["span_id"],"start":raw["start"],"end":raw["end"],
                "expected_text":expected_text,"kind":raw["kind"],"reason":raw["reason"],
                "decision":resolution,"created_at":iso(),
            }
            raw.update(state="resolved",resolution=resolution,updated_at=iso())
            s.get("privacy_plans",{}).pop(f"{raw['record_id']}:{raw['record_version']}",None)
            record["quarantined"]=True
            self._invalidate(s,privacy=True)
            return PrivacyDiagnostic.model_validate(raw)
    async def retry_job(self,ctx,job_id):
        async with self.transaction(ctx,admin=True) as (_,s):
            require(job_id in s["jobs"],"not_found");j=s["jobs"][job_id];p=j["public"]
            if p["state"]=="completed":return Job.model_validate(p)
            self._recoverable_cleanup(j)
            require(p["state"]=="failed" and p["retryable"],"invalid_input")
            require(j["lifecycle_revision"]==s["lifecycle_revision"],"evidence_changed")
            p.update(state="pending",error_code=None,retryable=False,updated_at=iso());j["lease_token"]=None
            for document_id in j["work"]["document_ids"]:
                if document_id in s["documents"]:s["documents"][document_id]["processing_state"]="pending"
            return Job.model_validate(p)

    def _conversation(self,s,ctx,conversation_id):
        conv=s["conversations"].get(conversation_id)
        require(conv and conv["owner_user_id"]==ctx.user_id and conv["project_id"]==ctx.project_id,"not_found")
        return conv
    async def create(self,ctx,title=None):
        if title is not None:require(1<=len(title)<=120,"invalid_input")
        async with self.transaction(ctx,write=True) as (_,s):
            conv=Conversation(id=uid(),project_id=ctx.project_id,owner_user_id=ctx.user_id,title="New Chat",created_at=iso(),updated_at=iso())
            s["conversations"][conv.id]=dump(conv);return conv
    async def list(self,ctx,page):
        async with self.transaction(ctx) as (_,s):
            items=[Conversation.model_validate(x) for x in s["conversations"].values() if x["owner_user_id"]==ctx.user_id]
            return self._page(sorted(items,key=lambda x:(x.created_at,x.id)),page,self._binding(ctx,s,"conversations"))
    def _answer(self,s,ctx,answer_id):
        a=s["answers"].get(answer_id);require(a,"not_found")
        self._conversation(s,ctx,a["data"]["conversation_id"])
        require(a["valid"] and a["data"]["snapshot"]==dump(self.snapshot(s)),"answer_unavailable")
        for dep in a["dependencies"]:self._dependency(s,Dependency.model_validate(dep))
        return Answer.model_validate(a["data"])
    async def messages(self,ctx,conversation_id,page):
        async with self.transaction(ctx) as (_,s):
            self._conversation(s,ctx,conversation_id);items=[]
            for raw in s["messages"].values():
                if raw["conversation_id"]!=conversation_id:continue
                msg=Message.model_validate(raw)
                if msg.answer_id:
                    try:self._answer(s,ctx,msg.answer_id)
                    except DomainError:msg.state="unavailable";msg.text=None;msg.answer_id=None;msg.unavailable_reason="evidence_changed"
                items.append(msg)
            return self._page(sorted(items,key=lambda x:(x.created_at,x.id)),page,self._binding(ctx,s,"messages",conversation_id))
    def _normalized(self,s,text):
        require(1<=len(text)<=8000,"invalid_input")
        return normalize(text,s["people"])
    async def begin_chat(self,ctx,input):
        async with self.transaction(ctx,write=True,fresh=True,restricted=True) as (_,s):
            self._conversation(s,ctx,input.conversation_id)
            key=compact([ctx.user_id,input.conversation_id,input.request_id]);digest=self.keyed(input.question)
            existing=s["attempts"].get(key)
            if existing:
                require(existing["input_hash"]==digest,"idempotency_conflict")
                if existing["state"]=="completed":return BeginChatReplay(answer=self._answer(s,ctx,existing["answer_id"]))
                require(existing["state"]!="running" or datetime.fromisoformat(existing["attempt"]["deadline"])<=now(),"request_in_progress")
                require(existing.get("retryable",True),"invalid_input")
            normalized=self._normalized(s,input.question)
            attempt=ChatAttempt(attempt_id=uid(),request_id=input.request_id,conversation_id=input.conversation_id,input_hash=digest,lease_token=secrets.token_urlsafe(32),deadline=now()+timedelta(seconds=self.request_deadline_seconds))
            history=[]
            for message in sorted(s["messages"].values(),key=lambda m:(m["created_at"],m["id"])):
                if message["conversation_id"]!=input.conversation_id or message["state"]!="available":continue
                if existing and message["id"]==existing["message_id"]:continue
                if message["role"]=="user":text=message["text"]
                else:
                    try:answer=self._answer(s,ctx,message["answer_id"])
                    except DomainError:continue
                    text="\n".join(c.text for c in answer.claims)
                history.append(HistoryTurn(message_id=message["id"],role=message["role"],text=normalize(text or "",s["people"]).text))
            mid=existing["message_id"] if existing else uid()
            s["messages"][mid]=dump(Message(id=mid,conversation_id=input.conversation_id,role="user",state="pending",text=normalized.text,answer_id=None,unavailable_reason=None,created_at=s["messages"][mid]["created_at"] if existing else iso()))
            s["attempts"][key]=dict(attempt=dump(attempt),input_hash=digest,state="running",message_id=mid,owner=ctx.user_id,snapshot=dump(self.snapshot(s)),access_revision=ctx.access_revision,retryable=True)
            return BeginChatReady(attempt=attempt,input=AnswerInput(question=normalized,history=history,request_id=input.request_id,conversation_id=input.conversation_id,deadline=attempt.deadline))
    def _attempt(self,s,ctx,attempt):
        self._conversation(s,ctx,attempt.conversation_id)
        key=compact([ctx.user_id,attempt.conversation_id,attempt.request_id]);a=s["attempts"].get(key)
        require(a and a["attempt"]==dump(attempt) and a["state"]=="running","evidence_changed")
        require(attempt.deadline>now(),"evidence_changed");return a
    def _dependency(self,s,dep,staged=False):
        r=s["records"].get(dep.record_id);require(r,"evidence_changed")
        if not staged:self._record(s,dep.record_id)
        require(r["record_version"]==dep.record_version,"evidence_changed")
        require(set(dep.span_ids)<=set(x["span_id"] for x in r["spans"]),"contract_violation")
        return r
    def _validate_candidate(self,s,project_id,candidate):
        require(candidate.snapshot==self.snapshot(s),"evidence_changed")
        require(candidate_digest(candidate)==candidate.candidate_digest)
        claims={c.id:c for c in candidate.claims};receipts={r.id:r for r in candidate.receipts}
        require(len(claims)==len(candidate.claims) and len(receipts)==len(candidate.receipts))
        used={rid for c in candidate.claims for rid in c.receipt_ids}
        require(used==set(receipts) and all(c.receipt_ids and len(c.receipt_ids)==len(set(c.receipt_ids)) for c in candidate.claims))
        for dep in candidate.dependencies:self._dependency(s,dep)
        depmap={(d.record_id,d.record_version):set(d.span_ids) for d in candidate.dependencies}
        for receipt in candidate.receipts:
            canonical=self._receipt(s,project_id,receipt.evidence_ref)
            require(dump(receipt)==dump(canonical))
            require(set(receipt.evidence_ref.span_ids)<=depmap.get((receipt.evidence_ref.record_id,receipt.evidence_ref.record_version),set()))
        for coverage in candidate.coverage.records:
            r=self._record(s,coverage.record_id);require(r["record_version"]==coverage.record_version,"evidence_changed")
            require(coverage.total_chunks==len(r["chunk_ids"]) and set(coverage.supplied_chunk_ids)<=set(r["chunk_ids"]))
            require(not coverage.complete or set(coverage.supplied_chunk_ids)==set(r["chunk_ids"]))
        if not candidate.claims:require(not candidate.receipts);return
        require(candidate.retrieval_review and candidate.retrieval_review.verdict=="sufficient")
        reviewed=candidate;results=candidate.review_results;digest=candidate.candidate_digest
        if candidate.omission_proof:
            proof=candidate.omission_proof;reviewed=proof.reviewed;results=proof.review_results;digest=proof.reviewed_digest
            require(candidate_digest(reviewed)==digest)
            for field in ("dependencies","coverage","cannot_establish","snapshot"):require(getattr(reviewed,field)==getattr(candidate,field))
            original_claims={c.id:c for c in reviewed.claims};original_receipts={r.id:r for r in reviewed.receipts}
            require(all(original_claims.get(c.id)==c for c in candidate.claims))
            require(all(original_receipts.get(r.id)==r for r in candidate.receipts))
            passed={r.claim_id for r in results if r.verdict=="pass"}
            require(all(c.id in claims for c in reviewed.claims if c.id in passed))
        results_by_id={}
        for result in results:
            require(result.claim_id not in results_by_id and result.candidate_digest==digest)
            results_by_id[result.claim_id]=result
        require(set(results_by_id)=={c.id for c in reviewed.claims})
        for claim in candidate.claims:
            result=results_by_id[claim.id]
            require(result.verdict=="pass" and result.receipt_ids==claim.receipt_ids)
    async def release_answer(self,ctx,attempt,candidate):
        async with self.transaction(ctx,write=True,fresh=True) as (_,s):
            a=self._attempt(s,ctx,attempt)
            require(a["snapshot"]==dump(self.snapshot(s)) and a["access_revision"]==ctx.access_revision,"evidence_changed")
            self._validate_candidate(s,ctx.project_id,candidate)
            answer=Answer(id=uid(),conversation_id=attempt.conversation_id,request_id=attempt.request_id,claims=candidate.claims,receipts=candidate.receipts,coverage=candidate.coverage,cannot_establish=candidate.cannot_establish,snapshot=candidate.snapshot,created_at=iso())
            s["answers"][answer.id]=dict(data=dump(answer),dependencies=[dump(d) for d in candidate.dependencies],valid=True)
            mid=uid();s["messages"][mid]=dump(Message(id=mid,conversation_id=attempt.conversation_id,role="assistant",state="available",text=None,answer_id=answer.id,unavailable_reason=None,created_at=iso()))
            s["messages"][a["message_id"]]["state"]="available"
            a.update(state="completed",answer_id=answer.id);s["conversations"][attempt.conversation_id]["updated_at"]=iso()
            return answer
    async def fail_chat(self,ctx,attempt,code):
        async with self.transaction(ctx) as (_,s):
            a=self._attempt(s,ctx,attempt);a["state"]="failed"
            a["retryable"]=code in ("provider_unavailable","dependency_unavailable","evidence_changed","internal_error")
            s["messages"][a["message_id"]]["state"]="failed"
    async def get_answer(self,ctx,answer_id):
        async with self.transaction(ctx) as (_,s):return self._answer(s,ctx,answer_id)
    async def get_receipt(self,ctx,answer_id,receipt_id):
        async with self.transaction(ctx) as (_,s):
            try:answer=self._answer(s,ctx,answer_id)
            except DomainError as e:
                if e.code=="answer_unavailable":raise DomainError("source_unavailable") from None
                raise
            receipt=next((r for r in answer.receipts if r.id==receipt_id),None);require(receipt,"not_found")
            require(receipt==self._receipt(s,ctx.project_id,receipt.evidence_ref),"source_unavailable")
            return receipt

    def _matches(self,s,r,entry,filters):
        if filters.record_type and r["record_type"]!=filters.record_type:return False
        if filters.original_doc_id and r["original_doc_id"]!=filters.original_doc_id:return False
        if filters.person_id and filters.person_id not in entry["person_ids"]:return False
        if filters.topic_id and filters.topic_id not in entry["topic_ids"]:return False
        if filters.date_from or filters.date_to:
            import calendar
            st=r["source_time"];value=st["value"]
            if st["precision"]=="unknown":return False
            try:
                if st["precision"]=="year":lo=date(int(value),1,1);hi=date(int(value),12,31)
                elif st["precision"]=="month":
                    year,month=map(int,value.split("-"));lo=date(year,month,1);hi=date(year,month,calendar.monthrange(year,month)[1])
                else:lo=hi=date.fromisoformat(value[:10])
            except (ValueError,TypeError):return False
            if filters.date_from and lo<filters.date_from:return False
            if filters.date_to and hi>filters.date_to:return False
        return True
    def _candidate(self,s,ref,filters):
        entry=s["entries"].get(ref.entry_id)
        if not entry or any(entry[k]!=getattr(ref,k) for k in ("record_id","record_version","chunk_id","input_hash")):return None
        try:r=self._record(s,ref.record_id)
        except DomainError:return None
        if r["record_version"]!=ref.record_version or ref.entry_id not in r["entry_ids"] or not self._matches(s,r,entry,filters):return None
        spans=[x for x in r["spans"] if x["span_id"] in entry["span_ids"]]
        return CanonicalCandidate(candidate=ref,record=self._summary(r),snippet="\n".join(x["text"] for x in spans)[:600],span_ids=[x["span_id"] for x in spans])
    async def lexical_candidates(self,ctx,normalized_query,filters,limit):
        require(1<=limit<=100 and 1<=len(normalized_query)<=8000,"invalid_input")
        async with self.transaction(ctx,fresh=True) as (c,s):
            # PostgreSQL ranks canonical concatenated memory/chunk inputs, not index payload text.
            candidates=[]
            for entry in s["entries"].values():
                ref=CandidateRef(entry_id=entry["id"],record_id=entry["record_id"],record_version=entry["record_version"],chunk_id=entry["chunk_id"],input_hash=entry["input_hash"],rank=1)
                if self._candidate(s,ref,filters):
                    ch=s["chunks"][entry["chunk_id"]];r=s["records"][entry["record_id"]];spans={x["span_id"]:x["text"] for x in r["spans"]}
                    text="\n\n".join([s["memories"][ch["level1_memory_id"]]["data"]["text"],s["memories"][ch["level2_memory_id"]]["data"]["text"],"\n".join(spans[x["span_id"]][x["start"]:x["end"]] for x in ch["slices"])])
                    candidates.append(dict(ref=dump(ref),text=text))
            rows=await (await c.execute("SELECT item->'ref' AS ref, ts_rank_cd(to_tsvector('simple',item->>'text'),websearch_to_tsquery('simple',%s)) AS score FROM jsonb_array_elements(%s::jsonb) item WHERE to_tsvector('simple',item->>'text') @@ websearch_to_tsquery('simple',%s) OR strpos(lower(item->>'text'),lower(%s))>0 ORDER BY score DESC,item->'ref'->>'entry_id' LIMIT %s",(normalized_query,Jsonb(candidates),normalized_query,normalized_query,limit))).fetchall()
            return [CandidateRef(**dict(row["ref"],rank=i+1)) for i,row in enumerate(rows)]
    async def validate_candidates(self,ctx,candidates,filters):
        async with self.transaction(ctx,fresh=True) as (_,s):
            eligible=[];rejected=[]
            for ref in candidates:
                item=self._candidate(s,ref,filters)
                if item:eligible.append(item)
                else:rejected.append(ref.entry_id)
            return CandidateCheck(eligible=eligible,rejected_entry_ids=rejected)
    async def read_history(self,ctx,query,page):
        async with self.transaction(ctx,fresh=True) as (_,s):
            items=[]
            for raw in s["history"].values():
                event=HistoryEvent.model_validate(raw)
                if event.topic_id!=query.topic_id or event.scope!=query.scope or event.review_state!="passed":continue
                try:
                    for ref in event.evidence:self._receipt(s,ctx.project_id,ref)
                except DomainError:continue
                items.append(event)
            result=self._page(sorted(items,key=lambda e:(e.learned_at,e.id)),page,self._binding(ctx,s,"history",dump(query)))
            return HistoryPage(items=result.items,next_cursor=result.next_cursor,coverage=Coverage(state="partial" if result.next_cursor else "complete",records=[],limitations=[]))

    def _cap(self,s,cap):
        j=s["jobs"].get(cap.job_id);require(j,"capability_denied")
        require(j["public"]["state"]=="running" and j["lease_token"]==cap.lease_token and j["expires_at"] and datetime.fromisoformat(j["expires_at"])>now(),"lease_lost")
        require(cap.expires_at>now() and j["lifecycle_revision"]==s["lifecycle_revision"]==cap.lifecycle_revision and cap.allowed_stage==j["public"]["stage"],"capability_denied")
        require(s["capabilities"].get(cap.capability_id)==dump(cap),"capability_denied")
        return j
    @asynccontextmanager
    async def cap_transaction(self,cap):
        async with self.db.connection(restricted=True) as c:
            s=await self.load_relational_project(c,cap.project_id,restricted=True,for_update=True);require(s,"capability_denied")
            self._cap(s,cap);yield c,s
            await self.sync_relational(c,cap.project_id,s,restricted=True)

    def _staged(self,s,cap,ref):
        require(ref in cap.allowed_record_versions,"capability_denied")
        r=s["records"].get(ref.record_id);require(r and r["record_version"]==ref.record_version,"evidence_changed")
        require(not r.get("quarantined"),"capability_denied")
        return StagedRecord(**{key:r[key] for key in StagedRecord.model_fields})
    async def load_staged_record(self,cap,ref):
        async with self.cap_transaction(cap) as (_,s):return self._staged(s,cap,ref)
    async def published_context(self,cap):
        async with self.cap_transaction(cap) as (_,s):
            return WorkReadContext(project_id=cap.project_id,job_id=cap.job_id,capability_id=cap.capability_id,snapshot=self.snapshot(s))
    async def load_rebuild_plan(self,cap,plan_id):
        async with self.cap_transaction(cap) as (_,s):
            require(plan_id in s["jobs"][cap.job_id]["work"]["rebuild_plan_ids"],"capability_denied")
            plan=RebuildPlan.model_validate(s["plans"][plan_id])
            require(plan.snapshot==self.snapshot(s),"evidence_changed")
            for dep in plan.dependencies:self._dependency(s,dep)
            return plan
    def _checkpoint(self,s,cap,key):
        saved=s["checkpoints"].get(compact([cap.job_id,key]))
        if saved:
            decoded=json.loads(key)
            if decoded[0]=="aggregate":
                require(decoded[1] in s["plans"] and s["plans"][decoded[1]]["snapshot"]==dump(self.snapshot(s)),"evidence_changed")
            require(saved["lifecycle_revision"]==cap.lifecycle_revision,"evidence_changed")
            for dep in saved["batch"]["dependencies"]:
                self._dependency(s,Dependency.model_validate(dep),staged=True)
            return StagedArtifacts.model_validate(saved)
        return None
    async def load_staged_artifacts(self,cap,artifact_key):
        async with self.cap_transaction(cap) as (_,s):return self._checkpoint(s,cap,artifact_key)
    def _validate_batch(self,s,cap,key,batch):
        require(batch.job_id==cap.job_id and batch.project_id==cap.project_id)
        try:decoded=json.loads(key)
        except Exception:raise DomainError("contract_violation") from None
        require(compact(decoded)==key)
        if decoded[0]=="record":
            require(len(decoded)==3)
            ref=RecordVersionRef(record_id=decoded[1],record_version=decoded[2]);self._staged(s,cap,ref)
        elif decoded[0]=="aggregate":
            require(len(decoded)==2 and decoded[1] in s["jobs"][cap.job_id]["work"]["rebuild_plan_ids"])
        else:raise DomainError("contract_violation")
        for dep in batch.dependencies:self._dependency(s,dep,staged=True)
        memories={m.id:m for m in batch.memories}
        require(len(memories)==len(batch.memories))
        for m in batch.memories:
            require(m.project_id==cap.project_id and m.dependencies)
            for d in m.dependencies:
                self._dependency(s,d,staged=True)
                require(any(d.record_id==x.record_id and d.record_version==x.record_version and set(d.span_ids)<=set(x.span_ids) for x in batch.dependencies))
        chunks={x.id:x for x in batch.chunks};require(len(chunks)==len(batch.chunks))
        for ch in batch.chunks:
            r=self._staged(s,cap,RecordVersionRef(record_id=ch.record_id,record_version=ch.record_version))
            spans={sp.span_id:sp for sp in r.spans}
            require(ch.slices and ch.level1_memory_id in memories and ch.level2_memory_id in memories)
            require(memories[ch.level1_memory_id].level==1 and memories[ch.level2_memory_id].level==2)
            order=[]
            for sl in ch.slices:
                require(sl.span_id in spans and 0<=sl.start<=sl.end<=len(spans[sl.span_id].text))
                order.append((spans[sl.span_id].ordinal,sl.start))
            require(order==sorted(order))
            text=memories[ch.level1_memory_id].text+"\n\n"+memories[ch.level2_memory_id].text+"\n\n"+"\n".join(spans[sl.span_id].text[sl.start:sl.end] for sl in ch.slices)
            require(hashlib.sha256(text.encode()).hexdigest()==ch.input_hash)
        entries={e.id:e for e in batch.index_entries};require(len(entries)==len(batch.index_entries))
        for e in batch.index_entries:
            require(e.project_id==cap.project_id and e.publication_generation==cap.publication_generation and e.chunk_id in chunks and e.embedding_dimension>0)
            ch=chunks[e.chunk_id];r=s["records"][e.record_id]
            require(e.record_version==ch.record_version and e.record_id==ch.record_id and e.input_hash==ch.input_hash and e.original_doc_id==r["original_doc_id"] and e.person_ids==r["person_ids"] and dump(e.source_time)==r["source_time"])
            require(e.span_ids==list(dict.fromkeys(sl.span_id for sl in ch.slices)))
            require(e.id==make_entry_id(e.project_id,e.record_id,e.record_version,e.chunk_id,e.input_hash,e.embedding_model,e.embedding_dimension))
        if decoded[0]=="record":
            require(batch.chunks and {c.record_id for c in batch.chunks}=={decoded[1]} and len(entries)==len(chunks))
            require(sorted(c.ordinal for c in batch.chunks)==list(range(len(batch.chunks))))
            # Coverage intervals must account for every source character, including blank spans.
            r=s["records"][decoded[1]]
            for span in r["spans"]:
                if not span["text"]: continue
                intervals=sorted((sl.start,sl.end) for ch in batch.chunks for sl in ch.slices if sl.span_id==span["span_id"])
                require(intervals);covered=0
                for start,end in intervals:require(start<=covered);covered=max(covered,end)
                require(covered==len(span["text"]))
        for event in batch.proposed_history:
            require(event.review_state in ("pending","passed","failed"))
            for ref in event.evidence:
                r=s["records"].get(ref.record_id);require(r and ref.project_id==cap.project_id and ref.original_doc_id==r["original_doc_id"] and ref.record_version==r["record_version"])
                require(set(ref.span_ids)<=set(x["span_id"] for x in r["spans"]))
    async def stage_artifacts(self,cap,artifact_key,batch):
        async with self.cap_transaction(cap) as (_,s):
            self._validate_batch(s,cap,artifact_key,batch)
            old=self._checkpoint(s,cap,artifact_key)
            if old:require(old.batch==batch);return old
            require(not any(v["batch"]["batch_id"]==batch.batch_id for v in s["checkpoints"].values()))
            saved=StagedArtifacts(artifact_key=artifact_key,batch=batch,lifecycle_revision=cap.lifecycle_revision,publication_generation=cap.publication_generation)
            s["checkpoints"][compact([cap.job_id,artifact_key])]=dump(saved)
            return saved
    async def release_overview(self,cap,input):
        async with self.cap_transaction(cap) as (_,s):
            self._validate_candidate(s,cap.project_id,input.candidate)
            require(any(input.memory_id in [m["id"] for m in saved["batch"]["memories"]] for saved in s["checkpoints"].values() if saved["batch"]["job_id"]==cap.job_id))
            s["jobs"][cap.job_id]["staged_overview"]=dict(id=input.memory_id,candidate=dump(input.candidate))
            return Overview(state="ready",id=input.memory_id,claims=input.candidate.claims,receipts=input.candidate.receipts,coverage=input.candidate.coverage,snapshot=self.snapshot(s),error_code=None)

class Reader:
    def __init__(self,platform):self.p=platform
    async def read_record(self,ctx,record_id,page):
        async with self.p.transaction(ctx,fresh=True) as (_,s):
            r=self.p._record(s,record_id);rp=self.p._record_page(s,ctx,r,page)
            mids={mid for chunk_id in rp.returned_chunk_ids for mid in (s["chunks"][chunk_id]["level1_memory_id"],s["chunks"][chunk_id]["level2_memory_id"])}
            return MemoryPage(record_page=rp,memories=[Memory.model_validate(s["memories"][mid]["data"]) for mid in sorted(mids) if s["memories"][mid]["valid"]])
    async def read_memory(self,ctx,memory_id):
        async with self.p.transaction(ctx,fresh=True) as (_,s):
            raw=s["memories"].get(memory_id);require(raw,"not_found");require(raw["valid"],"source_unavailable")
            memory=Memory.model_validate(raw["data"])
            for dep in memory.dependencies:self.p._dependency(s,dep)
            return memory
    async def expand_context(self,ctx,ref,before=2,after=2):
        require(0<=before<=20 and 0<=after<=20,"invalid_input")
        async with self.p.transaction(ctx,fresh=True) as (_,s):
            self.p._receipt(s,ctx.project_id,ref)
            r=self.p._record(s,ref.record_id);spans=r["spans"];idx=next(i for i,x in enumerate(spans) if x["span_id"]==ref.span_ids[0])
            binding=self.p._binding(ctx,s,"source",[r["record_id"],r["record_version"],ref.span_ids[0],before+after+len(ref.span_ids)])
            return self.p._source_page(s,ctx,r,ref.span_ids[0],before+after+len(ref.span_ids),self.p._cursor(binding,max(0,idx-before)))
    async def normalize_query(self,ctx,text):
        async with self.p.transaction(ctx,fresh=True,restricted=True) as (_,s):return self.p._normalized(s,text)
    async def make_receipt(self,ctx,ref):
        async with self.p.transaction(ctx,fresh=True) as (_,s):return self.p._receipt(s,ctx.project_id,ref)
