"""Create only this run's synthetic PostgreSQL project/accounts; no mock services."""
import asyncio, json, os, re, secrets
from pathlib import Path
from dotenv import load_dotenv

async def main():
    from app.evidence.postgres import Postgres
    from app.evidence.service import EvidencePlatform
    load_dotenv(override=False)
    run=os.environ["RELEX_RUN_ID"]
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}",run): raise ValueError("run ID must use lowercase letters/numbers/underscores")
    directory=Path(".runtime")/("c_"+run);directory.mkdir(parents=True,exist_ok=True)
    config_path=directory/"private.json"
    if config_path.exists():
        config=json.loads(config_path.read_text())
    else:
        config={"schema":"c_live_"+run,"collection":"c_live_"+run,"secret":secrets.token_urlsafe(48),
            "password":secrets.token_urlsafe(24),"admin_email":"admin-"+run+"@synthetic.invalid",
            "member_email":"member-"+run+"@synthetic.invalid","outsider_email":"outsider-"+run+"@synthetic.invalid"}
    db=Postgres(os.environ.get("RELEX_DATABASE_URL",""),config["schema"])
    await db.migrate()
    platform=EvidencePlatform(db,config["secret"])
    admin=await platform.bootstrap_user(config["admin_email"],config["password"],"Synthetic Admin")
    member=await platform.bootstrap_user(config["member_email"],config["password"],"Synthetic Member")
    outsider=await platform.bootstrap_user(config["outsider_email"],config["password"],"Synthetic Outsider")
    project=await platform.bootstrap_project("Synthetic "+run,admin,config.get("project_id"))
    login=await platform.login(config["admin_email"],config["password"])
    who=await platform.authenticate(login.session_token)
    ctx=await platform.authorize(who,project,"admin")
    await platform.set_member(ctx,member,"member")
    await platform.logout(who)
    other=await platform.bootstrap_project("Other synthetic "+run,admin,config.get("other_project_id"))
    config.update(project_id=project,other_project_id=other,admin_id=admin,member_id=member,outsider_id=outsider)
    config_path.write_text(json.dumps(config));config_path.chmod(0o600)
    print(json.dumps({"state":"prepared","schema":config["schema"],"project_id":project,"collection":config["collection"]}))
asyncio.run(main())
