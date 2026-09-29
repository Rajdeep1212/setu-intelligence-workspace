"""A separate, local PostgreSQL database for staging the scheme corpus (M2.1).

The application database is never a target. Every operation checks that the
database is named ``setu_corpus_staging`` or ``setu_corpus_staging_<suffix>``,
that the host is a loopback address, and, after connecting, that the server
reports the same database name.

The staging schema is the application schema: db/init.sql, then migration
0001 (jurisdiction, dates, source hash) and 0002 (version history), each
applied only when it is missing. Neither init.sql (CREATE TRIGGER) nor 0001
(ADD CONSTRAINT) can run twice.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILES = (
    ("init.sql", ROOT / "db" / "init.sql", "SELECT to_regclass('documents') IS NOT NULL"),
    (
        "0001_jurisdiction_and_effective_dates.up.sql",
        ROOT / "db" / "migrations" / "0001_jurisdiction_and_effective_dates.up.sql",
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()"
        " AND table_name = 'documents' AND column_name = 'source_hash')",
    ),
    (
        "0002_document_version_history.up.sql",
        ROOT / "db" / "migrations" / "0002_document_version_history.up.sql",
        "SELECT to_regclass('document_versions') IS NOT NULL",
    ),
)
STAGING_DATABASE_PATTERN = re.compile(r"^setu_corpus_staging(?:_[a-z0-9_]+)?$")


class StagingDatabaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalDatabaseConfig:
    user: str
    password: str
    host: str
    port: int

    @classmethod
    def from_env_file(cls, path: str | Path = ".env") -> "LocalDatabaseConfig":
        """Local Docker Compose credentials; the host is always 127.0.0.1."""
        values: dict[str, str] = {}
        env_path = Path(path)
        if env_path.is_file():
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
        config = cls(
            user=values.get("POSTGRES_USER", "setu"),
            password=values.get("POSTGRES_PASSWORD", "setu"),
            host="127.0.0.1",
            port=int(values.get("DATABASE_PORT", "5432")),
        )
        config.assert_loopback()
        return config

    def assert_loopback(self) -> None:
        try:
            address = ipaddress.ip_address(self.host)
        except ValueError as exc:
            raise StagingDatabaseError("Staging database host must be a loopback IP address") from exc
        if not address.is_loopback:
            raise StagingDatabaseError("Staging database operations are restricted to loopback")

    def connection_kwargs(self, database: str) -> dict[str, object]:
        self.assert_loopback()
        return {
            "user": self.user,
            "password": self.password,
            "host": self.host,
            "port": self.port,
            "database": database,
            "server_settings": {"application_name": "setu-corpus-staging"},
        }


def assert_staging_database_name(database_name: str) -> None:
    if not STAGING_DATABASE_PATTERN.fullmatch(database_name):
        raise StagingDatabaseError("Database name must match setu_corpus_staging[_suffix]")


async def apply_schema(connection) -> list[str]:
    """Apply init.sql, 0001 and 0002 where missing; return the files applied."""
    applied = []
    for name, path, is_applied in SCHEMA_FILES:
        if await connection.fetchval(is_applied):
            continue
        try:
            await connection.execute(path.read_text(encoding="utf-8"))
        except Exception:
            # Like psql -v ON_ERROR_STOP=1: abandon the failed file's transaction.
            await connection.execute("ROLLBACK")
            raise
        applied.append(name)
    return applied


async def _connect_admin(config: LocalDatabaseConfig) -> asyncpg.Connection:
    return await asyncpg.connect(**config.connection_kwargs("postgres"))


async def connect_staging(config: LocalDatabaseConfig, database_name: str) -> asyncpg.Connection:
    assert_staging_database_name(database_name)
    connection = await asyncpg.connect(**config.connection_kwargs(database_name))
    actual = await connection.fetchval("SELECT current_database()")
    if actual != database_name:
        await connection.close()
        raise StagingDatabaseError(f"Connected database {actual!r} does not match the staging target")
    return connection


async def staging_pool(config: LocalDatabaseConfig, database_name: str) -> asyncpg.Pool:
    """A small pool for ingestion.db_writer, after the name and host checks."""
    connection = await connect_staging(config, database_name)
    await connection.close()
    return await asyncpg.create_pool(min_size=1, max_size=2, **config.connection_kwargs(database_name))


async def prepare_staging_database(config: LocalDatabaseConfig, database_name: str) -> dict[str, object]:
    assert_staging_database_name(database_name)
    admin = await _connect_admin(config)
    created = False
    try:
        exists = await admin.fetchval("SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = $1)", database_name)
        if not exists:
            await admin.execute(f'CREATE DATABASE "{database_name}" TEMPLATE template0 ENCODING \'UTF8\'')
            created = True
    finally:
        await admin.close()
    connection = await connect_staging(config, database_name)
    try:
        applied = await apply_schema(connection)
        return {"database_name": database_name, "created": created, "applied": applied, "counts": await staging_counts(connection)}
    finally:
        await connection.close()


async def staging_counts(connection) -> dict[str, int]:
    return {
        table: await connection.fetchval(f"SELECT count(*) FROM {table}")
        for table in ("documents", "chunks", "document_versions")
    }


async def drop_staging_database(config: LocalDatabaseConfig, database_name: str, *, confirmation: str) -> None:
    assert_staging_database_name(database_name)
    if confirmation != database_name:
        raise StagingDatabaseError("Exact staging database name confirmation is required")
    admin = await _connect_admin(config)
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
    finally:
        await admin.close()
