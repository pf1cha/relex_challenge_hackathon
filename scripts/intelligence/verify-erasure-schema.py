"""Focused actual erasure-rebuild check for nested maintenance schema repair."""
import asyncio,json,os,secrets
from pathlib import Path
from dotenv import load_dotenv
from app.contracts.models import *
from app.contracts.errors import DomainError

async def main():
    load_dotenv(override=False)
    run='b_erasure_nested'
    folder=Path('scripts/intelligence/runs')/run;folder.mkdir(exist_ok=True)
    os.environ.update(RELEX_DATABASE_URL='postgresql://relex_dev@127.0.0.1:15432/postgres',RELEX_DATABASE_SCHEMA=run,
      RELEX_QDRANT_URL='http://127.0.0.1:16333',RELEX_QDRANT_COLLECTION=run,RELEX_SESSION_SECRET=secrets.token_hex(32),RELEX_LOOPBACK_HTTP='1',RELEX_REQUEST_TIMEOUT_SECONDS='240')
    from app.bootstrap import build_runtime
    from app.evidence.jobs import run_once
    runtime=build_runtime();p=runtime.evidence;report={'schema':run,'collection':run,'substitutes':[],'diagnostics':[]}
    original=runtime.intelligence.process_record
    async def diagnosed(cap,ref):
        try:return await original(cap,ref)
        except DomainError as exc:
            report['diagnostics'].append({'code':exc.code,'diagnostic':getattr(exc,'diagnostic',{})});raise
    runtime.intelligence.process_record=diagnosed
    try:
        await p.db.migrate();password=secrets.token_urlsafe(24)
        uid=await p.bootstrap_user(secrets.token_hex(8)+'@synthetic.invalid',password,'Synthetic Admin')
        pid=await p.bootstrap_project('Nested schema erasure probe',uid)
        async with p.db.connection() as conn:email=(await(await conn.execute('SELECT email FROM users WHERE id=%s',(uid,))).fetchone())['email']
        login=await p.login(email,password);principal=await p.authenticate(login.session_token);ctx=await p.authorize(principal,pid)
        person=await p.associate_person(ctx,PersonInput(display_name='Race Person',kind='employee',contacts=[Contact(kind='email',value='race@synthetic.invalid')]))
        job=await p.submit_upload(ctx,UploadInput(filename='race-source.txt',record_type='report',content=b'Date: 2026-09-01\nRace Person (race@synthetic.invalid) agreed Finland launch Helsinki first, requiring warehouse confirmation.'))
        for _ in range(20):
            await run_once(p,runtime.intelligence,'b-schema-upload');ctx=await p.authorize(principal,pid);state=await p.get_job(ctx,job.id)
            if state.state in ['completed','failed']:break
        assert state.state=='completed',state.error_code
        report['upload_job']=state.model_dump(mode='json')
        for _ in range(10):
            if not await run_once(p,runtime.intelligence,'b-schema-aggregate'):break
        ctx=await p.authorize(principal,pid);erasure=await p.erase_person(ctx,person.id)
        for _ in range(20):
            await run_once(p,runtime.intelligence,'b-schema-erasure');ctx=await p.authorize(principal,pid);state=await p.get_job(ctx,erasure.id)
            if state.state in ['completed','failed']:break
        report['erasure_job']=state.model_dump(mode='json');assert state.state=='completed',state.error_code
        documents=await p.list_documents(ctx,PageRequest(limit=100));texts=[]
        for document in documents.items:
            records=await p.list_records(ctx,document.id,PageRequest(limit=100))
            for record in records.items:
                page=await p.reader.read_record(ctx,record.record_id,PageRequest(limit=100));texts.extend(span.text for span in page.record_page.spans)
        assert '[deleted user]' in '\n'.join(texts) and 'Race Person' not in '\n'.join(texts) and 'race@synthetic.invalid' not in '\n'.join(texts)
        assert 'warehouse confirmation' in '\n'.join(texts)
        report.update(status='PASS',project_id=pid,decision_and_condition_preserved=True,person_attribution_replaced=True)
    except Exception as exc:
        report.update(status='FAIL',error=getattr(exc,'code',type(exc).__name__))
        raise
    finally:
        report['provider_events']=runtime.provider.events;(folder/'live.json').write_text(json.dumps(report,indent=2));await runtime.close()
    print(json.dumps({'status':report['status'],'report':str(folder/'live.json')}))
asyncio.run(main())
