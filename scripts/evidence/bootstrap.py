#!/usr/bin/env python3
"""Explicit account/project bootstrap; password is prompted or read from an env key."""
import argparse, asyncio, getpass, os
from app.evidence.postgres import Postgres
from app.evidence.service import EvidencePlatform
async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--email",required=True);parser.add_argument("--display-name",required=True)
    parser.add_argument("--project");parser.add_argument("--project-id");parser.add_argument("--password-env")
    args=parser.parse_args()
    password=os.environ.get(args.password_env,"") if args.password_env else getpass.getpass("New account password: ")
    db=Postgres(os.environ.get("RELEX_DATABASE_URL",""),os.environ.get("RELEX_DATABASE_SCHEMA","relex"))
    await db.migrate()
    p=EvidencePlatform(db,os.environ["RELEX_SECRET"])
    user=await p.bootstrap_user(args.email,password,args.display_name)
    project=await p.bootstrap_project(args.project,user,args.project_id) if args.project else None
    print({"user_id":user,"project_id":project})
if __name__=="__main__":asyncio.run(main())
