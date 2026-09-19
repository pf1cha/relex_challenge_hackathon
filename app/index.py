"""Qdrant holds concatenated memory packages; PostgreSQL controls eligibility."""
import os
import httpx
from . import provider
COLLECTION='relex_product_v1'
def call(method,path,data=None):
    url=os.environ.get('RELEX_QDRANT_URL') or 'http://127.0.0.1:26335'
    headers={}
    if os.environ.get('RELEX_QDRANT_API_KEY'):headers['api-key']=os.environ['RELEX_QDRANT_API_KEY']
    with httpx.Client(timeout=60) as client:
        r=client.request(method,url+path,json=data,headers=headers)
        r.raise_for_status();return r.json()
def ensure():
    collections=call('GET','/collections')['result']['collections']
    if not any(c['name']==COLLECTION for c in collections):call('PUT','/collections/'+COLLECTION,{'vectors':{'size':1536,'distance':'Cosine'}})
def upsert(points):
    if points:call('PUT','/collections/'+COLLECTION+'/points?wait=true',{'points':points})
def delete(ids):
    if ids:call('POST','/collections/'+COLLECTION+'/points/delete?wait=true',{'points':ids})
def search(project,query,limit=100):
    vector=provider.embed([query])[0]
    return call('POST','/collections/'+COLLECTION+'/points/query',{'query':vector,'filter':{'must':[{'key':'project_id','match':{'value':project}}]},'limit':limit,'with_payload':True})['result']['points']
