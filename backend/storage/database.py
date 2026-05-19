from __future__ import annotations
import contextlib
from typing import AsyncIterator
import aiosqlite
from pathlib import Path

_DB_PATH: Path = Path("pydataflow.db")


def set_db_path(path: Path) -> None:
    global _DB_PATH
    _DB_PATH = path


@contextlib.asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Async context manager yielding an aiosqlite connection with Row factory set."""
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        yield db


async def init_db() -> None:
    async with get_db() as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS workflows (
                workflow_id TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                data        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS custom_tools (
                tool_id     TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                data        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS run_history (
                run_id       TEXT PRIMARY KEY,
                workflow_id  TEXT NOT NULL,
                status       TEXT NOT NULL,
                started_at   TEXT NOT NULL,
                finished_at  TEXT NOT NULL,
                summary      TEXT NOT NULL
            );
        """)
        await db.commit()
