#!/usr/bin/env python3
import asyncio,os
from app.evidence.postgres import Postgres
if __name__=="__main__":
    asyncio.run(Postgres(os.environ.get("RELEX_DATABASE_URL",""),os.environ.get("RELEX_DATABASE_SCHEMA","relex")).migrate())
