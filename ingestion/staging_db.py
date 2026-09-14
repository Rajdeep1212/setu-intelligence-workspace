"""Guarded local PostgreSQL staging lifecycle for corpus experiments."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path

import asyncpg
from sqlalchemy import URL


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
            raise StagingDatabaseError("Staging database host must be a loopback IP") from exc
        if not address.is_loopback:
            raise StagingDatabaseError("Staging database operations are restricted to loopback")

    def connection_kwargs(self, database: str) -> dict[str, str | int]:
        return {
            "user": self.user,
            "password": self.password,
            "host": self.host,
            "port": self.port,
            "database": database,
            "server_settings": {"application_name": "setu-corpus-staging"},
        }

    def sqlalchemy_url(self, database: str) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=database,
        )


def assert_staging_database_name(database_name: str) -> None:
    if not STAGING_DATABASE_PATTERN.fullmatch(database_name):
        raise StagingDatabaseError(
            "Database name must match setu_corpus_staging[_suffix]"
        )


async def prepare_staging_database(
    config: LocalDatabaseConfig,
    database_name: str,
    schema_path: str | Path = "db/init.sql",
) -> dict[str, object]:
    assert_staging_database_name(database_name)
    admin = await asyncpg.connect(**config.connection_kwargs("postgres"))
    created = False
    try:
        exists = await admin.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=$1)",
            database_name,
        )
        if not exists:
            await admin.execute(f'CREATE DATABASE "{database_name}" TEMPLATE template0 ENCODING \'UTF8\'')
            created = True
    finally:
        await admin.close()

    connection = await connect_staging(config, database_name)
    try:
        schema = Path(schema_path).read_text(encoding="utf-8")
        await connection.execute(schema)
        extensions = await connection.fetch(
            "SELECT extname, extversion FROM pg_extension "
            "WHERE extname IN ('vector', 'pgcrypto') ORDER BY extname"
        )
        counts = await staging_counts(connection)
        return {
            "database_name": database_name,
            "created": created,
            "extensions": [dict(row) for row in extensions],
            "counts": counts,
        }
    finally:
        await connection.close()


async def connect_staging(
    config: LocalDatabaseConfig, database_name: str
) -> asyncpg.Connection:
    assert_staging_database_name(database_name)
    connection = await asyncpg.connect(**config.connection_kwargs(database_name))
    actual = await connection.fetchval("SELECT current_database()")
    if actual != database_name:
        await connection.close()
        raise StagingDatabaseError(
            f"Connected database {actual!r} does not match staging target"
        )
    return connection


async def staging_counts(connection: asyncpg.Connection) -> dict[str, int]:
    return {
        table: await connection.fetchval(f"SELECT count(*) FROM {table}")
        for table in ("documents", "chunks", "eligibility_criteria")
    }


async def staging_metrics(
    config: LocalDatabaseConfig, database_name: str
) -> dict[str, object]:
    connection = await connect_staging(config, database_name)
    try:
        counts = await staging_counts(connection)
        database_bytes = await connection.fetchval(
            "SELECT pg_database_size(current_database())"
        )
        corpus_bytes = await connection.fetchval(
            "SELECT coalesce(sum(octet_length(raw_text)), 0) FROM documents"
        )
        return {
            "database_name": database_name,
            "counts": counts,
            "database_bytes": database_bytes,
            "raw_text_bytes": corpus_bytes,
        }
    finally:
        await connection.close()


async def drop_staging_database(
    config: LocalDatabaseConfig,
    database_name: str,
    *,
    confirmation: str,
) -> None:
    assert_staging_database_name(database_name)
    if confirmation != database_name:
        raise StagingDatabaseError("Exact staging database name confirmation is required")
    admin = await asyncpg.connect(**config.connection_kwargs("postgres"))
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
    finally:
        await admin.close()
