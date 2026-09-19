"""Real server, two real workers, actual providers/index, browser-controlled faults."""
import asyncio,json,os,socket,subprocess,sys
from pathlib import Path
from dotenv import load_dotenv

async def main():
    load_dotenv(override=False)
    run=os.environ.get("RELEX_RUN_ID","c_browser_races")
    os.environ["RELEX_RUN_ID"]=run
    if not os.environ.get("RELEX_REUSE_LIVE_CONFIG"):
        subprocess.run([sys.executable,"scripts/product/prepare-live.py"],check=True)
    directory=Path(".runtime")/("c_"+run);config=json.loads((directory/"private.json").read_text())
    controls=directory/"controls";controls.mkdir(exist_ok=True)
    with socket.socket() as s:s.bind(("127.0.0.1",0));port=s.getsockname()[1]
    os.environ.update(RELEX_DATABASE_SCHEMA=config["schema"],RELEX_QDRANT_COLLECTION=config["collection"],
        RELEX_SESSION_SECRET=config["secret"],RELEX_LOOPBACK_HTTP="1",RELEX_TRUSTED_ORIGINS=f"http://127.0.0.1:{port}",
        RELEX_LIVE_URL=f"http://127.0.0.1:{port}",RELEX_LIVE_CONFIG=str((directory/"private.json").resolve()),
        RELEX_FAULT_CONTROLS=str(controls.resolve()),RELEX_REQUEST_TIMEOUT_SECONDS="300")
    from app.bootstrap import build_runtime
    from app.main import create_app
    from app.evidence.jobs import run_once
    sys.path.insert(0,str(Path.cwd()/"backend"/"tests"/"product"))
    from live_faults import PausedIntelligence,pause_index
    import uvicorn
    runtime=build_runtime()
    services=runtime.services
    services.intelligence=PausedIntelligence(runtime.intelligence,controls)
    pause_index(runtime.index,controls)
    server=uvicorn.Server(uvicorn.Config(create_app(services,runtime.settings.http),host="127.0.0.1",port=port,access_log=False,log_level="warning"))
    stop=asyncio.Event()
    async def worker(name):
        while not stop.is_set():
            if not await run_once(runtime.evidence,runtime.intelligence,name):await asyncio.sleep(.1)
    tasks=[asyncio.create_task(server.serve()),asyncio.create_task(worker("race-one")),asyncio.create_task(worker("race-two"))]
    try:
        while not server.started:await asyncio.sleep(.05)
        browser=await asyncio.create_subprocess_exec("node",os.environ.get("RELEX_BROWSER_DRIVER","scripts/product/browser-races.mjs"),env=dict(os.environ))
        result=await browser.wait()
        from psycopg import sql
        async with runtime.evidence.db.connection() as conn:
            row=await(await conn.execute("SELECT data FROM projects WHERE id=%s",(config["project_id"],))).fetchone()
            state=row["data"]
        (directory/"race-stores.json").write_text(json.dumps({
            "schema":config["schema"],"collection":config["collection"],"project_id":config["project_id"],
            "write_barrier":state["write_barrier"],"operations":[o["public"] for o in state["operations"].values()],
            "answers":len(state["answers"]),"current_entries":len(state["entries"])} ,indent=2))
        return result
    finally:
        stop.set();server.should_exit=True
        for task in tasks[1:]:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await runtime.close()
if __name__=="__main__":raise SystemExit(asyncio.run(main()))
