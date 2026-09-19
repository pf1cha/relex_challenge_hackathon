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
        restricted_schema = schema + "_restricted"
        if len(restricted_schema) > 63:
            raise ValueError("schema name leaves no room for restricted boundary")
        self.dsn, self.schema, self.restricted_schema = dsn, schema, restricted_schema
        self._pool = AsyncConnectionPool(conninfo=dsn,kwargs={"row_factory":dict_row},min_size=0,max_size=4,open=False)
        self._opened = False

    @asynccontextmanager
    async def connection(self):
        if not self._opened:
            await self._pool.open()
            self._opened = True
        async with self._pool.connection() as conn:
            await conn.execute(sql.SQL("SET search_path TO {}, {}, public").format(
                sql.Identifier(self.schema), sql.Identifier(self.restricted_schema)))
            yield conn

    async def migrate(self):
        async with self.connection() as conn:
            await conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))
            await conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.restricted_schema)))
            path = Path(__file__).resolve().parents[2] / "migrations"
            for migration in sorted(path.glob("*.sql")):
                parts = migration.read_text().split("{restricted}")
                statement = sql.Composed(sum(([sql.SQL(part), sql.Identifier(self.restricted_schema)] for part in parts[:-1]), []) + [sql.SQL(parts[-1])])
                await conn.execute(statement)

    async def ready(self):
        async with self.connection() as conn:
            row = await (await conn.execute("SELECT max(version) AS version FROM schema_migrations")).fetchone()
            return (row["version"] or 0) >= 3

    async def close(self):
        if self._opened:
            await self._pool.close()
            self._opened = False
