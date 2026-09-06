from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .config import settings
from .database import engine

LEGACY_TABLES = {"users", "nodes", "game_servers", "audit_logs"}


def _config() -> Config:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def run_migrations() -> None:
    tables = set(inspect(engine).get_table_names())
    config = _config()

    # Pre-Alembic StorServer installations already have the 0.1 schema.
    # Stamp those databases once, then use normal migrations from that point on.
    if "alembic_version" not in tables and tables.intersection(LEGACY_TABLES):
        if not LEGACY_TABLES.issubset(tables):
            missing = ", ".join(sorted(LEGACY_TABLES - tables))
            raise RuntimeError(f"Legacy StorServer schema is incomplete; missing: {missing}")
        command.stamp(config, "0001")

    command.upgrade(config, "head")
