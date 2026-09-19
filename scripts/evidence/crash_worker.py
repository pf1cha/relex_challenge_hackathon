"""Actual process interruption at real checkpoint/index acknowledgement boundaries."""
import asyncio,json,os,sys
from pathlib import Path
from live_helpers import build
from app.evidence.jobs import run_once
async def main():
    schema,mode,path=sys.argv[1:]
    p,b,provider,index=build(schema,os.environ["A_LIVE_SECRET"],lease_seconds=15)
    out=Path(path)
    def capture():
        out.write_text(json.dumps({"events":provider.events,"mode":mode}))
        os._exit(77)
    if mode=="checkpoint":
        original=p.stage_artifacts
        async def save(*args):
            result=await original(*args);capture();return result
        p.stage_artifacts=save
    elif mode=="ack":
        original=p.ledger.report
        async def report(*args):
            await original(*args);capture()
        p.ledger.report=report
    try:
        await run_once(p,b,"a-crash-worker")
        out.write_text(json.dumps({"events":provider.events,"mode":mode}))
    finally:
        await provider.close();await index.close();await p.db.close()
asyncio.run(main())
