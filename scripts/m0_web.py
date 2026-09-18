"""Temporary M0 connectivity page, not the product or a dependency health check."""
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
if not os.environ.get('SLURM_JOB_ID'):
    raise RuntimeError('Run on an allocated compute node')
app = FastAPI()
@app.get('/', response_class=HTMLResponse)
def page():
    return '<!doctype html><html lang="en"><title>RELEX connectivity check</title><h1>RELEX remote route works</h1><p>M0 connectivity probe only. Product and model verification are not complete.</p></html>'
@app.get('/health')
def health():
    return {'probe': 'connectivity', 'product_ready': False, 'model_verified': False}
