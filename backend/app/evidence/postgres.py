"""Native PostgreSQL persistence. No configuration reads or connections at import."""
from contextlib import asynccontextmanager
from pathlib import Path
import re
from psycopg import sql
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

class Postgres:
    def __init__(self, dsn: str = "", schema: str = "relex", restricted_dsn: str = ""):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
            raise ValueError("invalid schema")
        restricted_schema = schema + "_restricted"
        if len(restricted_schema) > 63:
            raise ValueError("schema name leaves no room for restricted boundary")
        self.dsn, self.restricted_dsn = dsn, restricted_dsn or dsn
        self.schema, self.restricted_schema = schema, restricted_schema
        kwargs={"row_factory":dict_row}
        self._pool = AsyncConnectionPool(conninfo=dsn,kwargs=kwargs,min_size=0,max_size=4,open=False)
        self._restricted_pool = AsyncConnectionPool(conninfo=self.restricted_dsn,kwargs=kwargs,min_size=0,max_size=2,open=False)
        self._opened = self._restricted_opened = False

    @asynccontextmanager
    async def connection(self, *, restricted=False):
        if restricted:
            if not self._restricted_opened:
                await self._restricted_pool.open()
                self._restricted_opened = True
            pool=self._restricted_pool
        else:
            if not self._opened:
                await self._pool.open()
                self._opened = True
            pool=self._pool
        async with pool.connection() as conn:
            if restricted:
                search_path=sql.SQL("SET search_path TO {}, {}, public").format(
                    sql.Identifier(self.schema),sql.Identifier(self.restricted_schema))
            else:
                search_path=sql.SQL("SET search_path TO {}, public").format(sql.Identifier(self.schema))
            await conn.execute(search_path)
            yield conn

    async def migrate(self):
        async with self.connection(restricted=True) as conn:
            await conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))
            await conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.restricted_schema)))
            path = Path(__file__).resolve().parents[2] / "migrations"
            for migration in sorted(path.glob("*.sql")):
                version=int(migration.name.split("_",1)[0])
                table=await (await conn.execute("SELECT to_regclass('schema_migrations') AS name")).fetchone()
                if table["name"] is not None:
                    current=await (await conn.execute("SELECT COALESCE(max(version),0) AS version FROM schema_migrations")).fetchone()
                    if current["version"]>=version:continue
                parts = migration.read_text().split("{restricted}")
                statement = sql.Composed(sum(([sql.SQL(part), sql.Identifier(self.restricted_schema)] for part in parts[:-1]), []) + [sql.SQL(parts[-1])])
                await conn.execute(statement)

    async def ready(self):
        async with self.connection() as conn:
            row = await (await conn.execute("SELECT max(version) AS version FROM schema_migrations")).fetchone()
            return (row["version"] or 0) >= 4

    async def close(self):
        if self._opened:
            await self._pool.close()
            self._opened = False
        if self._restricted_opened:
            await self._restricted_pool.close()
            self._restricted_opened = False
