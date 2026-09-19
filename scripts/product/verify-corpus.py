"""Real Acme corpus ingestion verification; never substitutes provider responses."""
import asyncio,json,os,secrets,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
from dotenv import load_dotenv
from app.bootstrap import build_runtime
from app.contracts.models import PersonInput,UploadInput,PageRequest
from app.evidence.jobs import run_once

async def main():
 load_dotenv(".env")
 run="corpus_"+datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
 out=Path("artifacts/corpus")/run;out.mkdir(parents=True)
 os.environ.update(RELEX_DATABASE_URL="postgresql://relex_dev@127.0.0.1:15432/postgres",RELEX_DATABASE_SCHEMA=run,RELEX_QDRANT_URL="http://127.0.0.1:16333",RELEX_QDRANT_COLLECTION=run,RELEX_SESSION_SECRET=secrets.token_urlsafe(48))
 rt=build_runtime();p=rt.evidence
 await p.db.migrate()
 password=secrets.token_urlsafe(24)
 user=await p.bootstrap_user("corpus-verifier@example.test",password,"Corpus verifier")
 project=await p.bootstrap_project("Acme corpus verification",user)
 login=await p.login("corpus-verifier@example.test",password);principal=await p.authenticate(login.session_token)
 async def ctx():return await p.authorize(principal,project)
 names=["Lena Fischer","Robert Kahn","Sofia Almeida","Priya Nair","Jonas Weiss","Katarina Voss","Marco Rossi","Ana Duarte","Nadia Haddad","Tomas Lindholm","Kwame Boateng","Charlotte Meyer","Henrik Sørensen","Ivan Petrov","Ruth Oyelaran"]
 for i,name in enumerate(names):await p.associate_person(await ctx(),PersonInput(display_name=name,kind="client" if i<6 else "employee",contacts=[]))
 report={"run_id":run,"schema":run,"project_id":project,"source":"corpus/acme","documents":[],"practice_questions":"BLOCKED until corpus publication and provider availability","source_files_modified":False}
 try:
  for path in sorted(Path("corpus/acme").glob("*/*.txt")):
   data=path.read_bytes()
   kind={"emails":"email","transcripts":"transcript","reports":"report"}[path.parent.name]
   job=await p.submit_upload(await ctx(),UploadInput(filename=path.name,record_type=kind,content=data))
   for _ in range(12):
    status=await p.get_job(await ctx(),job.id)
    if status.state in ("completed","failed"):break
    await run_once(p,rt.intelligence,"corpus-verifier")
   row={"file":str(path),"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data),"job_id":job.id,"state":status.state,"stage":status.stage,"error":status.error_code}
   report["documents"].append(row)
   (out/"report.json").write_text(json.dumps(report,indent=2))
   print(json.dumps(row),flush=True)
  report["summary"]={key:sum(r["error"]==key for r in report["documents"]) for key in set(r["error"] for r in report["documents"])}
  report["status"]="PASS" if all(r["state"]=="completed" for r in report["documents"]) else "BLOCKED"
  (out/"report.json").write_text(json.dumps(report,indent=2))
  print("REPORT",str(out/"report.json"),json.dumps(report["summary"]),flush=True)
  return 0 if report["status"]=="PASS" else 2
 finally:await rt.close()
sys.exit(asyncio.run(main()))
