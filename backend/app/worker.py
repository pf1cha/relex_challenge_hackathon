"""Explicit durable worker process; no jobs launch on import."""
import asyncio
import os
import signal
from uuid import uuid4

async def run():
    from app.bootstrap import build_runtime
    from app.evidence.jobs import run_once
    runtime=build_runtime()
    stopping=asyncio.Event()
    loop=asyncio.get_running_loop()
    for sig in (signal.SIGINT,signal.SIGTERM):
        loop.add_signal_handler(sig,stopping.set)
    worker_id=os.environ.get("RELEX_WORKER_ID","worker-"+uuid4().hex)
    try:
        while not stopping.is_set():
            worked=await run_once(runtime.evidence,runtime.intelligence,worker_id)
            if not worked:
                try: await asyncio.wait_for(stopping.wait(),timeout=1)
                except TimeoutError: pass
    finally:
        await runtime.close()

if __name__=="__main__":
    asyncio.run(run())
