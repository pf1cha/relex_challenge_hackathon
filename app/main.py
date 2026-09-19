import hashlib
import hmac
import json
import secrets
import threading
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException,UploadFile,File,Form
from fastapi.responses import HTMLResponse,JSONResponse
from . import store,index,pipeline,privacy,agent,provider
app=FastAPI(title='Memory With a Receipt')

def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
def user(request):
    token=request.cookies.get('session','')
    with store.transaction() as c:
        row=c.execute('SELECT u.id,u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=%s AND expires>now()',(store.digest(token),)).fetchone()
    if not row:raise HTTPException(401,'Log in required')
    return row
def access(c,p,u,admin=False):
    row=c.execute('SELECT role FROM memberships WHERE project_id=%s AND user_id=%s',(p,u['id'])).fetchone()
    if not row or (admin and row['role']!='admin'):raise HTTPException(403,'Project access denied')
    return row['role']
def launch(fn,*args):threading.Thread(target=fn,args=args,daemon=True).start()
@app.middleware('http')
async def same_origin(request,call_next):
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin.split('://')[-1]!=request.headers.get('host'):return JSONResponse({'detail':'Cross-origin mutation denied'},status_code=403)
    response=await call_next(request);response.headers['Cache-Control']='no-store';return response
@app.exception_handler(provider.ProviderError)
async def model_error(request,exc):return JSONResponse({'detail':str(exc)},status_code=503)
@app.exception_handler(ValueError)
async def value_error(request,exc):return JSONResponse({'detail':str(exc)},status_code=400)
@app.on_event('startup')
def startup():store.initialize();index.ensure()
@app.get('/',response_class=HTMLResponse)
def home():return (Path(__file__).parent/'ui.html').read_text()
@app.get('/health')
def health():
    result={}
    try:
        with store.transaction() as c:c.execute('SELECT 1')
        result['postgres']='ok'
    except Exception:result['postgres']='unavailable'
    try:index.call('GET','/collections');result['qdrant']='ok'
    except Exception:result['qdrant']='unavailable'
    return JSONResponse(result,status_code=200 if all(v=='ok' for v in result.values()) else 503)
@app.post('/api/login')
def login(body:dict):
    with store.transaction() as c:
        row=c.execute('SELECT * FROM users WHERE username=%s',(body.get('username',''),)).fetchone()
        if not row or not hmac.compare_digest(password_hash(body.get('password',''),row['password_hash'].split(':')[0]),row['password_hash']):raise HTTPException(401,'Invalid login')
        token=secrets.token_urlsafe(32);c.execute('INSERT INTO sessions VALUES(%s,%s,%s)',(store.digest(token),row['id'],datetime.now(timezone.utc)+timedelta(hours=12)))
    response=JSONResponse({'username':row['username']});response.set_cookie('session',token,httponly=True,samesite='strict',max_age=43200);return response
@app.post('/api/logout')
def logout(request:Request):
    with store.transaction() as c:c.execute('DELETE FROM sessions WHERE token_hash=%s',(store.digest(request.cookies.get('session','')),))
    response=JSONResponse({'ok':True});response.delete_cookie('session');return response
@app.get('/api/projects')
def projects(request:Request):
    u=user(request)
    with store.transaction() as c:return c.execute('SELECT p.*,m.role FROM projects p JOIN memberships m ON m.project_id=p.id WHERE m.user_id=%s ORDER BY p.name',(u['id'],)).fetchall()
@app.get('/api/projects/{p}/status')
def status(p:str,request:Request):
    u=user(request)
    with store.transaction() as c:
        role=access(c,p,u);docs=store.items(c,p,'document');visible=docs if role=='admin' else [d for d in docs if d['state']=='active']
        return {'documents':len(visible),'states':{s:sum(d['state']==s for d in visible) for s in ['active','inactive','processing','failed','deleting']},'visualization':'Project status only. Visualization content is deferred.','generation':store.generation(c,p)}
@app.get('/api/projects/{p}/documents')
def documents(p:str,request:Request):
    u=user(request)
    with store.transaction() as c:
        role=access(c,p,u);docs=store.items(c,p,'document')
        return [{k:v for k,v in d.items() if k!='raw'} for d in docs if role=='admin' or d['state']=='active']
@app.post('/api/projects/{p}/documents')
def upload(p:str,request:Request,file:UploadFile=File(...),kind:str=Form(...),inject_failure:bool=Form(False)):
    u=user(request)
    with store.transaction(p) as c:
        access(c,p,u,True)
        if kind not in ('email','report','transcript'):raise ValueError('Supported types: email, report, transcript')
        raw=file.file.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('Upload exceeds 2 MB')
        try:text=raw.decode('utf-8')
        except UnicodeDecodeError:raise ValueError('Only UTF-8 text accepted')
        doc={'id':store.uid(),'filename':'pending-document.txt','type':kind,'raw':text,'state':'processing'};store.put(c,p,'document',doc)
        job={'id':store.uid(),'document_id':doc['id'],'type':'upload','state':'pending','inject_failure':inject_failure};store.put(c,p,'job',job)
    launch(pipeline.process_upload,p,job['id']);return job
@app.get('/api/projects/{p}/jobs')
def jobs(p:str,request:Request):
    u=user(request)
    with store.transaction() as c:access(c,p,u,True);return store.items(c,p,'job')
@app.post('/api/projects/{p}/jobs/{id}/retry')
def retry(p:str,id:str,request:Request):
    u=user(request)
    with store.transaction(p) as c:
        access(c,p,u,True);job=store.get(c,p,'job',id)
        if not job or job['state']!='failed':raise ValueError('Only failed jobs can retry')
        job.update(state='pending',inject_failure=False,error=None);store.put(c,p,'job',job)
    launch(pipeline.delete_person if job['type']=='person_delete' else pipeline.process_upload,p,id);return job
@app.post('/api/projects/{p}/documents/{id}/{action}')
def document_action(p:str,id:str,action:str,request:Request):
    u=user(request)
    if action not in ('activate','deactivate','delete'):raise HTTPException(404)
    with store.transaction(p) as c:
        access(c,p,u,True);doc=store.get(c,p,'document',id)
        if not doc:raise HTTPException(404)
        pipeline.mutate_document(c,p,doc,action)
    return {'ok':True}
@app.get('/api/projects/{p}/records/{id}')
def record(p:str,id:str,request:Request,cursor:int=0):
    u=user(request)
    with store.transaction() as c:access(c,p,u);return privacy.display(c,p,agent.read(c,p,id,cursor))
@app.get('/source/{p}/{id}',response_class=HTMLResponse)
def source(p:str,id:str,request:Request,line:int=1,version:int=0):
    import html
    u=user(request)
    with store.transaction() as c:
        role=access(c,p,u);rec=store.get(c,p,'record',id)
        if not rec:raise HTTPException(404)
        doc=store.get(c,p,'document',rec['document_id'])
        if not doc or doc['state']!='active':
            if not (role=='admin' and doc and doc['state']=='inactive'):raise HTTPException(410,'Source unavailable')
        if version and rec['version']!=version:raise HTTPException(410,'Source changed; regenerate answer')
        text=privacy.display(c,p,rec['content'])
    return '<!doctype html><title>Source receipt</title><h1>Source receipt</h1><p>Original document '+html.escape(rec['original_doc_id'])+'</p><ol>'+''.join('<li id="line-'+str(i)+'" style="white-space:pre-wrap;'+('background:#fff2a8' if i==line else '')+'">'+html.escape(s)+'</li>' for i,s in enumerate(text.splitlines(),1))+'</ol>'
@app.get('/api/projects/{p}/records')
def records(p:str,request:Request):
    u=user(request)
    with store.transaction() as c:
        role=access(c,p,u);rs=pipeline.active_records(c,p)
        if role=='admin':rs=store.items(c,p,'record')
        return privacy.display(c,p,[{k:v for k,v in r.items() if k!='content'} for r in rs])
@app.post('/api/projects/{p}/search')
def search(p:str,body:dict,request:Request):
    u=user(request)
    with store.transaction() as c:access(c,p,u);gen=store.generation(c,p)
    with store.transaction() as c:result=agent.search(c,p,body.get('query',''),body.get('filters'))
    with store.transaction(p) as c:
        access(c,p,u)
        if store.generation(c,p)!=gen:raise HTTPException(409,'Evidence changed; retry')
        return privacy.display(c,p,result)
@app.get('/api/projects/{p}/topics')
def topics(p:str,request:Request):
    u=user(request)
    with store.transaction() as c:access(c,p,u);return privacy.display(c,p,store.items(c,p,'topic'))
@app.post('/api/projects/{p}/chat')
def chat(p:str,body:dict,request:Request):
    u=user(request)
    with store.transaction() as c:access(c,p,u)
    result=agent.answer(p,str(body.get('question',''))[:8000],max(1,min(int(body.get('read_budget',36)),60)))
    # Bounded diagnostic delay supports real race verification, admin only.
    delay=min(float(body.get('publish_delay',0)),15)
    if delay:
        with store.transaction() as c:access(c,p,u,True)
        time.sleep(delay)
    with store.transaction(p) as c:
        access(c,p,u)
        if store.generation(c,p)!=result['generation']:raise HTTPException(409,'Evidence or access changed; answer withheld')
        id=store.put(c,p,'chat',dict(result,user_id=u['id']));return dict(privacy.display(c,p,result),id=id)
@app.get('/api/projects/{p}/chat/{id}')
def saved_chat(p:str,id:str,request:Request):
    u=user(request)
    with store.transaction() as c:
        access(c,p,u);result=store.get(c,p,'chat',id)
        if not result:raise HTTPException(404)
        if result['user_id']!=u['id']:raise HTTPException(403)
        if result['generation']!=store.generation(c,p):raise HTTPException(410,'Evidence changed; regenerate')
        return privacy.display(c,p,result)
@app.post('/api/projects/{p}/review')
def review(p:str,body:dict,request:Request):
    u=user(request)
    with store.transaction() as c:access(c,p,u,True);gen=store.generation(c,p)
    result=agent.answer(p,body['question'],diagnostic_draft=body['draft'])
    with store.transaction(p) as c:
        access(c,p,u,True)
        if gen!=store.generation(c,p):raise HTTPException(409,'Evidence changed')
        return result
@app.get('/api/projects/{p}/people')
def people(p:str,request:Request):
    u=user(request)
    with store.transaction() as c:
        role=access(c,p,u);items=store.items(c,p,'person')
        return items if role=='admin' else [{'id':x['id'],'name':x['name']} for x in items]
@app.post('/api/projects/{p}/people')
def associate(p:str,body:dict,request:Request):
    u=user(request)
    with store.transaction(p) as c:
        access(c,p,u,True)
        if body.get('category') not in ('client','employee'):raise ValueError('Choose client or employee')
        person={'id':store.uid(),'name':body['name'],'aliases':[body['name']],'contacts':body.get('contacts',[]),'category':body['category'],'deleted':False};store.put(c,p,'person',person)
        return person
@app.post('/api/projects/{p}/people/{id}/delete')
def delete_person(p:str,id:str,body:dict,request:Request):
    u=user(request)
    with store.transaction(p) as c:
        access(c,p,u,True);person=store.get(c,p,'person',id)
        if not person or person.get('deleted'):raise ValueError('Person unavailable')
        if any(j.get('person_id')==id and j['state']!='completed' for j in store.items(c,p,'job')):raise ValueError('Deletion already in progress; retry existing job')
        job={'id':store.uid(),'type':'person_delete','person_id':id,'state':'pending','inject_failure':bool(body.get('inject_failure'))}
        affected={r['document_id'] for r in store.items(c,p,'record') if privacy.token(id) in json.dumps(r)}
        for doc in store.items(c,p,'document'):
            if doc['id'] in affected or (doc.get('raw') and any(s in doc['raw'] for s in person['aliases']+person['contacts'])):
                doc.update(previous_state=doc['state'],state='deleting',deletion_job=job['id']);store.put(c,p,'document',doc)
        # Inventory is durable through person mapping + doc job markers + unchanged SQL before commit.
        job['affected_document_ids']=sorted(affected);store.put(c,p,'job',job);store.bump(c,p)
        # Hide transitive topic summaries immediately; rebuild on successful deletion.
        for topic in store.items(c,p,'topic'):
            rids={d['record_id'] for d in topic['dependencies']}
            if any(r['id'] in rids and r['document_id'] in affected for r in store.items(c,p,'record')):store.remove(c,p,topic['id'])
    launch(pipeline.delete_person,p,job['id']);return job
@app.get('/api/projects/{p}/members')
def members(p:str,request:Request):
    u=user(request)
    with store.transaction() as c:access(c,p,u,True);return c.execute('SELECT u.username,m.role FROM memberships m JOIN users u ON u.id=m.user_id WHERE project_id=%s',(p,)).fetchall()
@app.post('/api/projects/{p}/members')
def member(p:str,body:dict,request:Request):
    u=user(request)
    with store.transaction(p) as c:
        access(c,p,u,True);target=c.execute('SELECT id FROM users WHERE username=%s',(body['username'],)).fetchone()
        if not target:raise ValueError('Unknown login account; create with bootstrap CLI')
        role=body['role']
        if role=='remove':c.execute('DELETE FROM memberships WHERE project_id=%s AND user_id=%s',(p,target['id']))
        elif role in ('admin','member'):c.execute('INSERT INTO memberships VALUES(%s,%s,%s) ON CONFLICT(project_id,user_id) DO UPDATE SET role=EXCLUDED.role',(p,target['id'],role))
        else:raise ValueError('Invalid role')
        store.bump(c,p)
    return {'ok':True}
