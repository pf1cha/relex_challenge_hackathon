"""Malformed real checkpoint rejection and lifecycle fencing, using real model artifacts."""
import argparse,asyncio,json,os,secrets,sys
from pathlib import Path
from live_helpers import build
from app.contracts.models import *
from app.contracts.errors import DomainError
async def main():
    parser=argparse.ArgumentParser();parser.add_argument("--run-id",required=True);args=parser.parse_args()
    schema="a_cap_"+args.run_id.lower().replace("-","_");secret=secrets.token_hex(32)
    p,b,provider,index=build(schema,secret,lease_seconds=15);await p.db.migrate()
    out=Path("artifacts/evidence")/args.run_id;out.mkdir(parents=True,exist_ok=True)
    pw=secrets.token_urlsafe(24);user=await p.bootstrap_user("admin@synthetic.invalid",pw,"Admin")
    project=await p.bootstrap_project("Capability synthetic",user)
    login=await p.login("admin@synthetic.invalid",pw);principal=await p.authenticate(login.session_token)
    ctx=await p.authorize(principal,project)
    job=await p.submit_upload(ctx,UploadInput(filename="Fenced checkpoint.txt",record_type="report",content=b"Date: 2026-09-01\nThe launch on 2026-10-01 is agreed."))
    try:
        child=await asyncio.create_subprocess_exec(sys.executable,"scripts/evidence/crash_worker.py",schema,"checkpoint",str(out/"checkpoint.json"),env=dict(os.environ,A_LIVE_SECRET=secret))
        assert await child.wait()==77
        async with p.db.connection() as c:
            s=(await (await c.execute("SELECT data FROM projects WHERE id=%s",(project,))).fetchone())["data"]
        cap=JobCapability.model_validate(next(v for v in s["capabilities"].values() if v["job_id"]==job.id))
        saved=StagedArtifacts.model_validate(next(v for v in s["checkpoints"].values() if v["batch"]["job_id"]==job.id))
        async def denied(code,coro):
            try:await coro
            except DomainError as e:assert e.code==code,(e.code,code);return
            raise AssertionError("expected "+code)
        assert (await p.load_staged_artifacts(cap,saved.artifact_key))==saved
        malformed=saved.batch.model_copy(deep=True);malformed.chunks[0].input_hash="0"*64
        await denied("contract_violation",p.stage_artifacts(cap,saved.artifact_key,malformed))
        changed=saved.batch.model_copy(deep=True);changed.memories[0].generator_version="changed-after-checkpoint"
        await denied("contract_violation",p.stage_artifacts(cap,saved.artifact_key,changed))
        doc=s["jobs"][job.id]["work"]["document_ids"][0]
        mutation=await p.mutate_document(await p.authorize(principal,project),doc,"deactivate")
        await denied("capability_denied",p.load_staged_artifacts(cap,saved.artifact_key))
        await denied("capability_denied",p.stage_artifacts(cap,saved.artifact_key,saved.batch))
        result=dict(status="PASS",cases=["CT-13","CT-17-lifecycle"],schema=schema,job_id=job.id,mutation_job_id=mutation.id,batch_id=saved.batch.batch_id,checks=["real checkpoint reload","wrong input hash rejected","same key changed metadata rejected","lifecycle invalidates old checkpoint read/write"])
        (out/"capability.json").write_text(json.dumps(result,indent=2));print(json.dumps(result))
    finally:await provider.close();await index.close();await p.db.close()
asyncio.run(main())
