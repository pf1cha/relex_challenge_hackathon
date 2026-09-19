"""Native PostgreSQL persistence. No configuration reads or connections at import."""
from contextlib import asynccontextmanager
from pathlib import Path
import re
from psycopg import sql
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

class Postgres:
    def __init__(self, dsn: str = "", schema: str = "relex"):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
            raise ValueError("invalid schema")
        self.dsn, self.schema = dsn, schema
        self._pool = AsyncConnectionPool(conninfo=dsn,kwargs={"row_factory":dict_row},min_size=0,max_size=4,open=False)
        self._opened = False

    @asynccontextmanager
    async def connection(self):
        if not self._opened:
            await self._pool.open()
            self._opened = True
        async with self._pool.connection() as conn:
            await conn.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(self.schema)))
            yield conn

    async def migrate(self):
        async with self.connection() as conn:
            await conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))
            path = Path(__file__).resolve().parents[2] / "migrations"
            for migration in sorted(path.glob("*.sql")):
                await conn.execute(migration.read_text())

    async def ready(self):
        async with self.connection() as conn:
            row = await (await conn.execute("SELECT max(version) AS version FROM schema_migrations")).fetchone()
            return row["version"] == 1

    async def close(self):
        if self._opened:
            await self._pool.close()
            self._opened = False
