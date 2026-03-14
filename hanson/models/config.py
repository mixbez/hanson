from __future__ import annotations

import json
import os
import tomllib
import dataclasses
from urllib.parse import urlparse


@dataclasses.dataclass(frozen=True)
class PostgresConfig:
    database: str
    user: str
    password: str
    host: str
    port: int = 5432


@dataclasses.dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


@dataclasses.dataclass(frozen=True)
class Config:
    postgres: PostgresConfig
    server: ServerConfig

    @staticmethod
    def load_from_toml_file(fname: str) -> Config:
        # Support DATABASE_URL env var (Supabase / Vercel-style)
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            return Config._from_database_url(database_url)

        try:
            with open(fname, "rb") as f:
                raw = tomllib.load(f)
        except FileNotFoundError:
            raise RuntimeError(
                f"Config file '{fname}' not found. "
                "Set DATABASE_URL environment variable or provide a config.toml."
            )

        assert "postgres" in raw
        assert "server" in raw

        if "password" not in raw["postgres"]:
            password = os.getenv("PGPASSWORD")
            assert password is not None, (
                "Postgres password must either be set in the config "
                "or be provided through PGPASSWORD."
            )
            raw["postgres"]["password"] = password

        return Config(
            postgres=PostgresConfig(**raw["postgres"]),
            server=ServerConfig(**raw["server"]),
        )

    @staticmethod
    def _from_database_url(url: str) -> Config:
        """Parse a DATABASE_URL like postgresql://user:pass@host:5432/dbname."""
        parsed = urlparse(url)
        return Config(
            postgres=PostgresConfig(
                database=parsed.path.lstrip("/"),
                user=parsed.username or "postgres",
                password=parsed.password or "",
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
            ),
            server=ServerConfig(
                host=os.environ.get("HOST", "0.0.0.0"),
                port=int(os.environ.get("PORT", "8080")),
            ),
        )

    def format_echo(self) -> str:
        as_dict = dataclasses.asdict(self)
        as_dict["postgres"]["password"] = "(redacted)"
        return json.dumps(as_dict, indent=2)
