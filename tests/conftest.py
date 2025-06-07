"""Ensure project root is on sys.path during pytest collection."""
import sys
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# use in-memory database for tests
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
import pytest
from alembic import command
from alembic.config import Config
from apps.worker import init_db as sync_init_db


@pytest.fixture(scope="session", autouse=True)
def apply_migrations() -> None:
    """Apply Alembic migrations before tests run."""

    try:
        import aiosqlite  # noqa: WPS433
    except ModuleNotFoundError:
        sync_init_db()
        yield
    else:
        cfg = Config(str(ROOT / "alembic.ini"))
        command.upgrade(cfg, "head")
        yield
