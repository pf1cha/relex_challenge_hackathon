"""Owned real-process/browser orchestration. Missing dependencies remain BLOCKED."""
import asyncio, json, os, socket, subprocess, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=False)
run=os.environ["RELEX_RUN_ID"]
directory=Path(".runtime")/("c_"+run);directory.mkdir(parents=True,exist_ok=True)
if (directory/"report.json").exists():
    from datetime import datetime,timezone
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    (directory/"report.json").rename(directory/("report-"+stamp+".json"))
report={"run_id":run,"requirements":{},"status":"running","revision":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()}
def block(reason):
    report.update(status="BLOCKED",reason=reason)
    for req in ["R-C1","R-C2","R-C3","R-C4","R-G1","R-G2","R-G3","R-G4","R-S"]:
        report["requirements"].setdefault(req,"BLOCKED: "+reason)
    (directory/"report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report));sys.exit(2)
try:
    from app.bootstrap import build_runtime
    from app.evidence.jobs import run_once
except ImportError:
    block("Actual A/B adapters are unavailable")
if not Path("frontend/dist/index.html").exists(): block("Build the actual frontend first")
if not os.environ.get("RELEX_QDRANT_URL"): block("Set RELEX_QDRANT_URL to an authorized real Qdrant service")
result=subprocess.run([sys.executable,"scripts/product/prepare-live.py"])
if result.returncode: block("PostgreSQL/migrations/bootstrap failed")
config=json.loads((directory/"private.json").read_text())
with socket.socket() as probe:
    probe.bind(("127.0.0.1",0));port=probe.getsockname()[1]
env=os.environ.copy()
env.update(RELEX_DATABASE_SCHEMA=config["schema"],RELEX_QDRANT_COLLECTION=config["collection"],
    RELEX_SESSION_SECRET=config["secret"],RELEX_LOOPBACK_HTTP="1",
    RELEX_TRUSTED_ORIGINS="http://127.0.0.1:"+str(port),RELEX_LIVE_URL="http://127.0.0.1:"+str(port),
    RELEX_LIVE_CONFIG=str((directory/"private.json").resolve()),RELEX_REQUEST_TIMEOUT_SECONDS="300")
log=(directory/"services.log").open("a")
http=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:production_app","--factory","--host","127.0.0.1","--port",str(port),"--no-access-log"],env=env,stdout=log,stderr=log)
worker=subprocess.Popen([sys.executable,"-m","app.worker"],env=env,stdout=log,stderr=log)
report.update(port=port,http_pid=http.pid,worker_pid=worker.pid,schema=config["schema"],collection=config["collection"],project_id=config["project_id"])
try:
    import httpx
    for attempt in range(60):
        if http.poll() is not None or worker.poll() is not None: block("Actual HTTP/worker process failed; inspect owned service log")
        try:
            if httpx.get(env["RELEX_LIVE_URL"]+"/health").status_code==200: break
        except httpx.HTTPError: pass
        time.sleep(.5)
    else: block("HTTP startup timed out")
    result=subprocess.run(["node","scripts/product/browser-live.mjs"],env=env)
    browser_report=directory/"browser.json"
    if browser_report.exists(): report.update(browser=json.loads(browser_report.read_text()))
    if result.returncode == 0:
        for process in [http,worker]:
            process.terminate()
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        http=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:production_app","--factory","--host","127.0.0.1","--port",str(port),"--no-access-log"],env=env,stdout=log,stderr=log)
        worker=subprocess.Popen([sys.executable,"-m","app.worker"],env=env,stdout=log,stderr=log)
        for attempt in range(60):
            try:
                if httpx.get(env["RELEX_LIVE_URL"]+"/health").status_code==200: break
            except httpx.HTTPError: pass
            time.sleep(.5)
        restart=subprocess.run(["node","scripts/product/browser-restart.mjs"],env=env)
        if (directory/"restart.json").exists(): report["restart"]=json.loads((directory/"restart.json").read_text())
        if restart.returncode: result=restart
        else:
            lifecycle=subprocess.run(["node","scripts/product/browser-lifecycle.mjs"],env=env)
            if (directory/"lifecycle.json").exists(): report["lifecycle"]=json.loads((directory/"lifecycle.json").read_text())
            if lifecycle.returncode: result=lifecycle
            else:
                http.terminate();http.wait(timeout=15)
                fault_env=env.copy()
                fault_env["RELEX_EMBEDDING_BASE_URL"]="http://127.0.0.1:1"
                http=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:production_app","--factory","--host","127.0.0.1","--port",str(port),"--no-access-log"],env=fault_env,stdout=log,stderr=log)
                for attempt in range(60):
                    try:
                        if httpx.get(env["RELEX_LIVE_URL"]+"/health").status_code==200: break
                    except httpx.HTTPError: pass
                    time.sleep(.5)
                fault=subprocess.run(["node","scripts/product/browser-provider-failure.mjs"],env=env)
                if (directory/"provider-failure.json").exists(): report["provider_failure"]=json.loads((directory/"provider-failure.json").read_text())
                if fault.returncode: result=fault
                else:
                    http.terminate();http.wait(timeout=15)
                    http=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:production_app","--factory","--host","127.0.0.1","--port",str(port),"--no-access-log"],env=env,stdout=log,stderr=log)
                    for attempt in range(60):
                        try:
                            if httpx.get(env["RELEX_LIVE_URL"]+"/health").status_code==200: break
                        except httpx.HTTPError: pass
                        time.sleep(.5)
                    recovery=subprocess.run(["node","scripts/product/browser-provider-recovery.mjs"],env=env)
                    if (directory/"provider-recovery.json").exists(): report["provider_recovery"]=json.loads((directory/"provider-recovery.json").read_text())
                    if recovery.returncode: result=recovery
    report["status"]="PARTIAL" if result.returncode==0 else "FAIL"
    report["requirements"]=report.get("browser",{}).get("requirements",{})
    if report.get("restart",{}).get("status")=="PASS":
        report["requirements"]["R-C1"]="LIVE: login/logout/CSRF/project boundaries plus persistent process restart"
        report["requirements"]["R-C3-restart"]="LIVE: persistent conversations, browser reload and project state clearing"
    if report.get("lifecycle",{}).get("status")=="PASS":
        report["requirements"]["R-C4"]="LIVE: denied admin calls, membership/association, same-name target erasure, deactivate/reactivate/delete; injected cleanup-failure retry UI pending"
    if report.get("provider_recovery",{}).get("status")=="PASS":
        report["requirements"]["R-C3-provider"]="LIVE: provider outage 503, safe retry UI, restored actual provider and same-request recovery"
    from psycopg import connect,sql
    with connect(os.environ.get("RELEX_DATABASE_URL","")) as connection:
        row=connection.execute(sql.SQL("SELECT data FROM {}.projects WHERE id=%s").format(sql.Identifier(config["schema"])),(config["project_id"],)).fetchone()
        state=row[0]
        report["canonical"]={"documents":len(state["documents"]),"records":len(state["records"]),
            "jobs":{key:sum(j["public"]["state"]==key for j in state["jobs"].values()) for key in ["pending","running","failed","completed"]},
            "checkpoints":len(state["checkpoints"]),"operations":len(state["operations"]),
            "answers":len(state["answers"]),"write_barrier":state["write_barrier"],
            "corpus_generation":state["corpus_generation"],"privacy_generation":state["privacy_generation"],
            "current_entries":len(state["entries"])}
    index_response=httpx.get(os.environ["RELEX_QDRANT_URL"].rstrip("/")+"/collections/"+config["collection"],
        headers={"api-key":os.environ.get("RELEX_QDRANT_API_KEY","")})
    if index_response.status_code==200:
        info=index_response.json()["result"]
        report["qdrant"]={"collection":config["collection"],"points_count":info["points_count"],"vectors":info["config"]["params"]["vectors"]}
    report["services"]={"generation_model":os.environ.get("RELEX_MODEL_NAME"),"embedding_model":os.environ.get("RELEX_EMBEDDING_MODEL"),
        "database_host":os.environ.get("PGHOST","native DSN"),"qdrant_url":os.environ["RELEX_QDRANT_URL"]}
    (directory/"report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report))
finally:
    for process in [http,worker]:
        process.terminate()
    for process in [http,worker]:
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.kill();process.wait()
    log.close()
sys.exit(2 if report["status"]=="PARTIAL" else 1)
