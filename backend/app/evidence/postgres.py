"""Native PostgreSQL persistence. No configuration reads or connections at import."""
from contextlib import asynccontextmanager
from pathlib import Path
import re
from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

class Postgres:
    def __init__(self, dsn: str = "", schema: str = "relex"):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
            raise ValueError("invalid schema")
        self.dsn, self.schema = dsn, schema

    @asynccontextmanager
    async def connection(self):
        async with await AsyncConnection.connect(self.dsn, row_factory=dict_row) as conn:
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
