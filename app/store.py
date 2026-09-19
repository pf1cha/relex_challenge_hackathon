"""PostgreSQL persistence. Mutations use per-project transaction advisory locks."""
import contextlib
import hashlib
import os
import uuid
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env',override=False)
def uid():return str(uuid.uuid4())
def connect():
    return psycopg.connect(os.environ.get('RELEX_DATABASE_URL', 'dbname=postgres host='+str(ROOT/'.runtime/product/socket')+' port=25433'),row_factory=dict_row)
def initialize():
    with connect() as c:c.execute((ROOT/'migrations/001.sql').read_text())
@contextlib.contextmanager
def transaction(project=None):
    with connect() as c:
        if project:c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(project,))
        yield c

def items(c,p,kind):return [dict(r['data'],id=r['id']) for r in c.execute('SELECT id,data FROM artifacts WHERE project_id=%s AND kind=%s ORDER BY id',(p,kind))]
def get(c,p,kind,id):
    r=c.execute('SELECT data FROM artifacts WHERE project_id=%s AND kind=%s AND id=%s',(p,kind,id)).fetchone()
    return dict(r['data'],id=id) if r else None
def put(c,p,kind,obj):
    obj=dict(obj); id=obj.pop('id',None) or uid()
    c.execute('INSERT INTO artifacts(id,project_id,kind,data) VALUES(%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET data=EXCLUDED.data',(id,p,kind,Jsonb(obj)))
    return id
def remove(c,p,id):c.execute('DELETE FROM artifacts WHERE project_id=%s AND id=%s',(p,id))
def generation(c,p):return c.execute('SELECT generation FROM projects WHERE id=%s',(p,)).fetchone()['generation']
def bump(c,p):c.execute('UPDATE projects SET generation=generation+1 WHERE id=%s',(p,))
def digest(text):return hashlib.sha256(text.encode()).hexdigest()
