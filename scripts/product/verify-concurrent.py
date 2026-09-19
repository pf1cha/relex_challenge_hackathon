"""G4 overlap orchestration, preserving individual nonzero/partial results."""
import json, os, subprocess
from pathlib import Path
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[2]
stamp=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
directory=root/".runtime"/("g4_"+stamp);directory.mkdir(parents=True)
common=os.environ.copy()
common.setdefault("RELEX_DATABASE_URL","postgresql://relex_dev@127.0.0.1:15432/postgres")
common.setdefault("RELEX_LIVE_DATABASE_URL",common["RELEX_DATABASE_URL"])
common.setdefault("RELEX_QDRANT_URL","http://127.0.0.1:16333")
commands={
 "A":["bash","scripts/evidence/verify-live.sh","--run-id","ag4_"+stamp],
 "B":["bash","scripts/intelligence/verify-live.sh","--run-id","bg4_"+stamp,"--case","B-C1"],
 "C":["bash","scripts/product/verify-live.sh","--run-id","cg4_"+stamp],
}
running={}
for owner,command in commands.items():
 log=(directory/(owner+".log")).open("w")
 process=subprocess.Popen(command,cwd=root,env=common,stdout=log,stderr=subprocess.STDOUT)
 running[owner]={"process":process,"log":log,"started_at":datetime.now(timezone.utc).isoformat(),"command":command,"pid":process.pid}
print(json.dumps({"directory":str(directory),"started":{k:{"pid":v["pid"],"command":v["command"]} for k,v in running.items()}}),flush=True)
report={"kind":"real_service_concurrency","started_at":stamp,"runners":{}}
for owner,value in running.items():
 status=value["process"].wait();value["log"].close()
 report["runners"][owner]={"command":value["command"],"pid":value["pid"],"started_at":value["started_at"],"observed_exit_at":datetime.now(timezone.utc).isoformat(),"exit_status":status,"log":str(directory/(owner+".log"))}
report["interpretation"]="All three actual live commands overlapped. Each runner's report controls behavioral acceptance; a partial/nonzero result is not a product pass."
(directory/"concurrency.json").write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
raise SystemExit(0 if all(v["exit_status"]==0 for v in report["runners"].values()) else 2)
