"""Real ASGI application factory with injected contract services."""
from __future__ import annotations
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, Request, Response, Depends, Query, UploadFile, File, Form
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from app.config import HttpSettings
from app.contracts.models import *
from app.contracts.ports import Services
from app.contracts.errors import DomainError
from app.api.schemas import LoginInput, RegisterInput, ConversationInput, MemberInput, SearchBody
from app.api.errors import error_response

def create_app(services: Services, settings: HttpSettings) -> FastAPI:
    app = FastAPI(title="Memory With a Receipt", version="5")
    app.state.services = services
    app.state.settings = settings

    @app.middleware("http")
    async def safety(request, call_next):
        # Reject declared oversized multipart bodies before Starlette spools them.
        # Exact file-byte enforcement remains in the route and canonical service.
        if request.method == "POST" and request.url.path.endswith("/documents"):
            length = request.headers.get("content-length")
            if length:
                try:
                    if int(length) > settings.upload_limit_bytes + 65536:
                        return error_response("upload_too_large")
                except ValueError:
                    return error_response("invalid_input")
        try:
            async with asyncio.timeout(settings.request_timeout_seconds):
                response = await call_next(request)
        except TimeoutError:
            response = error_response("dependency_unavailable")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        response = error_response(exc.code)
        if request.url.path == "/api/logout":
            response.delete_cookie("relex_session", path="/")
        return response
    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def invalid(request, exc):
        return error_response("invalid_input")
    @app.exception_handler(ResponseValidationError)
    async def invalid_output(request, exc):
        return error_response("contract_violation")
    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        return error_response("internal_error")

    def origin(request):
        if request.headers.get("origin") not in settings.trusted_origins:
            raise DomainError("csrf_failed")
    async def principal(request: Request):
        if request.method in ("POST", "DELETE"):
            origin(request)
        token = request.cookies.get("relex_session", "")
        who = await services.auth.authenticate(token)
        if request.method in ("POST", "DELETE"):
            await services.auth.validate_csrf(who, request.headers.get("x-csrf-token", ""))
        return who
    async def context(p: Id, who=Depends(principal)):
        return await services.projects.authorize(who, p)
    async def admin(p: Id, who=Depends(principal)):
        return await services.projects.authorize(who, p, "admin")
    def queries(request, allowed=()):
        if set(request.query_params) - set(allowed):
            raise DomainError("invalid_input")
    async def no_query(request: Request):
        queries(request)
    async def empty_body(request: Request):
        if await request.body():
            raise DomainError("invalid_input")
    async def page(request: Request, cursor: str | None=None, limit: Annotated[int, Query(ge=1,le=100)]=25):
        queries(request, ("cursor","limit"))
        return PageRequest(cursor=cursor, limit=limit)
    no_input=[Depends(no_query),Depends(empty_body)]

    @app.post("/api/login", response_model=Me, dependencies=[Depends(no_query)])
    async def login(body: LoginInput, request: Request, response: Response):
        origin(request)
        if request.headers.get("content-type","").split(";")[0] != "application/json":
            raise DomainError("invalid_input")
        old = request.cookies.get("relex_session")
        result = await services.auth.login(body.email, body.password)
        if old:
            try:
                await services.auth.logout(await services.auth.authenticate(old))
            except DomainError as exc:
                if exc.code != "unauthenticated": raise
        response.set_cookie("relex_session", result.session_token, httponly=True,
                            secure=settings.secure_cookie, samesite="lax", path="/")
        return result.me
    @app.post("/api/register", response_model=Me, status_code=201, dependencies=[Depends(no_query)])
    async def register(body: RegisterInput, request: Request, response: Response):
        origin(request)
        if request.headers.get("content-type","").split(";")[0] != "application/json":
            raise DomainError("invalid_input")
        result = await services.auth.register(body.email, body.password, body.display_name)
        old = request.cookies.get("relex_session")
        if old:
            try:
                await services.auth.logout(await services.auth.authenticate(old))
            except DomainError as exc:
                if exc.code != "unauthenticated": raise
        response.set_cookie("relex_session", result.session_token, httponly=True,
                            secure=settings.secure_cookie, samesite="lax", path="/")
        return result.me
    @app.post("/api/logout", status_code=204, dependencies=no_input)
    async def logout(who=Depends(principal)):
        await services.auth.logout(who)
        response=Response(status_code=204)
        response.delete_cookie("relex_session",path="/")
        return response
    @app.get("/api/me", response_model=Me, dependencies=[Depends(no_query)])
    async def me(who=Depends(principal)): return await services.auth.me(who)
    @app.get("/api/projects", response_model=Page[Project])
    async def projects(who=Depends(principal), paging=Depends(page)):
        return await services.projects.list_projects(who,paging)
    base="/api/projects/{p}"
    @app.get(base+"/documents", response_model=Page[Document])
    async def documents(ctx=Depends(context), paging=Depends(page)):
        return await services.documents.list_documents(ctx,paging)
    @app.get(base+"/documents/{id}/records", response_model=Page[RecordSummary])
    async def records(id: Id, ctx=Depends(context), paging=Depends(page)):
        return await services.documents.list_records(ctx,id,paging)
    @app.post(base+"/documents", response_model=Job, status_code=202, dependencies=[Depends(no_query)])
    async def upload(request: Request, file: UploadFile=File(), record_type: RecordType=Form(), ctx=Depends(admin)):
        form=await request.form()
        if set(form.keys()) != {"file","record_type"} or len(form.getlist("file")) != 1:
            raise DomainError("invalid_input")
        if not file.filename or len(file.filename)>255: raise DomainError("invalid_input")
        data=bytearray()
        try:
            while chunk:=await file.read(min(65536,settings.upload_limit_bytes+1-len(data))):
                data.extend(chunk)
                if len(data)>settings.upload_limit_bytes: raise DomainError("upload_too_large")
        finally: await file.close()
        return await services.documents.submit_upload(ctx,UploadInput(filename=file.filename,record_type=record_type,content=bytes(data)))
    def mutation(action):
        async def route(id: Id, ctx=Depends(admin)):
            return await services.documents.mutate_document(ctx,id,action)
        return route
    for action in ("activate","deactivate"):
        app.add_api_route(base+"/documents/{id}/"+action,mutation(action),methods=["POST"],response_model=Job,status_code=202,dependencies=no_input)
    app.add_api_route(base+"/documents/{id}",mutation("delete"),methods=["DELETE"],response_model=Job,status_code=202,dependencies=no_input)
    @app.get(base+"/records/{id}",response_model=RecordPage)
    async def record(id: Id,ctx=Depends(context),paging=Depends(page)):
        return await services.sources.read_record(ctx,id,paging)
    @app.get(base+"/sources/{id}",response_model=SourcePage)
    async def source(request: Request,id: Id,version: Annotated[int,Query(ge=1)],span: Id,
                     cursor: str|None=None,limit: Annotated[int,Query(ge=1,le=100)]=25,ctx=Depends(context)):
        queries(request,("version","span","cursor","limit"))
        return await services.sources.read_source(ctx,SourceRequest(record_id=id,version=version,span_id=span,cursor=cursor,limit=limit))
    @app.post(base+"/search",response_model=SearchPage,dependencies=[Depends(no_query)])
    async def search(body: SearchBody,ctx=Depends(context)):
        return await services.intelligence.search_memory(ctx,SearchInput(query=body.query,filters=body.filters,page=PageRequest(cursor=body.cursor,limit=body.limit)))
    @app.get(base+"/filters",response_model=FilterOptions,dependencies=[Depends(no_query)])
    async def filters(ctx=Depends(context)): return await services.sources.get_filters(ctx)
    @app.get(base+"/status",response_model=ProjectStatus,dependencies=[Depends(no_query)])
    async def status(ctx=Depends(context)): return await services.sources.get_status(ctx)
    @app.get(base+"/overview",response_model=Overview,dependencies=[Depends(no_query)])
    async def overview(ctx=Depends(context)): return await services.sources.get_overview(ctx)
    @app.post(base+"/conversations",response_model=Conversation,status_code=201,dependencies=[Depends(no_query)])
    async def create_conversation(body: ConversationInput,ctx=Depends(context)):
        return await services.conversations.create(ctx,body.title)
    @app.get(base+"/conversations",response_model=Page[Conversation])
    async def conversations(ctx=Depends(context),paging=Depends(page)):
        return await services.conversations.list(ctx,paging)
    @app.get(base+"/conversations/{id}/messages",response_model=Page[Message])
    async def messages(id: Id,ctx=Depends(context),paging=Depends(page)):
        return await services.conversations.messages(ctx,id,paging)
    @app.post(base+"/chat",response_model=Answer,dependencies=[Depends(no_query)])
    async def chat(body: ChatInput,ctx=Depends(context)):
        if not 1<=len(body.question)<=8000: raise DomainError("invalid_input")
        begin=await services.conversations.begin_chat(ctx,body)
        if begin.state=="replay": return begin.answer
        try:
            candidate=await services.intelligence.answer(ctx,begin.input)
            return await services.conversations.release_answer(ctx,begin.attempt,candidate)
        except BaseException as exc:
            code=exc.code if isinstance(exc,DomainError) else "internal_error"
            try:
                await asyncio.shield(services.conversations.fail_chat(ctx,begin.attempt,code))
            except BaseException: pass
            raise
    @app.get(base+"/answers/{id}",response_model=Answer,dependencies=[Depends(no_query)])
    async def answer(id: Id,ctx=Depends(context)): return await services.conversations.get_answer(ctx,id)
    @app.get(base+"/answers/{id}/receipts/{receipt_id}",response_model=Receipt,dependencies=[Depends(no_query)])
    async def receipt(id: Id,receipt_id: Id,ctx=Depends(context)):
        return await services.conversations.get_receipt(ctx,id,receipt_id)
    @app.get(base+"/members",response_model=Page[Member])
    async def members(ctx=Depends(admin),paging=Depends(page)): return await services.administration.list_members(ctx,paging)
    @app.post(base+"/members",response_model=Member,dependencies=[Depends(no_query)])
    async def set_member(body: MemberInput,ctx=Depends(admin)):
        if body.email is not None:
            return await services.administration.set_member_by_email(ctx,body.email,body.role)
        return await services.administration.set_member(ctx,body.user_id,body.role)
    @app.delete(base+"/members/{id}",status_code=204,dependencies=no_input)
    async def remove_member(id: Id,ctx=Depends(admin)):
        await services.administration.remove_member(ctx,id)
        return Response(status_code=204)
    @app.get(base+"/people",response_model=Page[Person])
    async def people(ctx=Depends(admin),paging=Depends(page)): return await services.administration.list_people(ctx,paging)
    @app.post(base+"/people",response_model=Person,dependencies=[Depends(no_query)])
    async def associate(body: PersonInput,ctx=Depends(admin)):
        if not 1<=len(body.display_name)<=255 or any(not 1<=len(c.value)<=500 for c in body.contacts):
            raise DomainError("invalid_input")
        return await services.administration.associate_person(ctx,body)
    @app.post(base+"/people/{id}/erase",response_model=Job,status_code=202,dependencies=no_input)
    async def erase(id: Id,ctx=Depends(admin)): return await services.administration.erase_person(ctx,id)
    @app.get(base+"/jobs",response_model=Page[Job])
    async def jobs(ctx=Depends(admin),paging=Depends(page)): return await services.administration.list_jobs(ctx,paging)
    @app.get(base+"/jobs/{id}",response_model=Job,dependencies=[Depends(no_query)])
    async def job(id: Id,ctx=Depends(admin)): return await services.administration.get_job(ctx,id)
    @app.post(base+"/jobs/{id}/retry",response_model=Job,dependencies=no_input)
    async def retry(id: Id,ctx=Depends(admin)): return await services.administration.retry_job(ctx,id)
    @app.get("/health")
    async def health():
        readiness=getattr(app.state,"readiness",None)
        if readiness is None:
            return {"database":"unconfigured","index":"unconfigured","model":"unverified"}
        return await readiness()
    dist=Path(settings.frontend_dist)
    if (dist/"assets").is_dir():
        app.mount("/assets",StaticFiles(directory=dist/"assets"),name="assets")
    @app.get("/",include_in_schema=False)
    async def shell():
        if not (dist/"index.html").exists(): raise DomainError("dependency_unavailable")
        return FileResponse(dist/"index.html",headers={"Cache-Control":"no-store"})
    for page_name in ("documents","search","chat","overview","visualization","administration"):
        app.add_api_route(f"/{page_name}",shell,methods=["GET"],include_in_schema=False)
    @app.get("/projects/{p}/sources/{id}",include_in_schema=False)
    async def source_shell(request: Request,p: Id,id: Id,version: Annotated[int,Query(ge=1)],span: Id):
        queries(request,("version","span"))
        return await shell()
    return app

def production_app():
    from app.bootstrap import build_runtime
    runtime=build_runtime()
    app=create_app(runtime.services,runtime.settings.http)
    app.state.runtime=runtime
    app.state.readiness=runtime.readiness
    @asynccontextmanager
    async def lifespan(app):
        try: yield
        finally: await runtime.close()
    app.router.lifespan_context=lifespan
    return app
