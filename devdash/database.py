"""SQLite database manager for caching, context memory, and standup history."""

from __future__ import annotations

import logging
from datetime import datetime

import aiosqlite

from devdash.config import AppConfig

log = logging.getLogger(__name__)

DB_PATH = "devdash.db"

SCHEMA = """
-- GitHub data cache
CREATE TABLE IF NOT EXISTS pr_cache (
    id INTEGER PRIMARY KEY,
    repo TEXT NOT NULL,
    number INTEGER NOT NULL,
    title TEXT,
    author TEXT,
    state TEXT,
    ci_status TEXT,
    summary TEXT,
    risk_score TEXT,
    updated_at TEXT,
    UNIQUE(repo, number)
);

CREATE TABLE IF NOT EXISTS ci_cache (
    id INTEGER PRIMARY KEY,
    repo TEXT NOT NULL,
    run_id INTEGER NOT NULL,
    status TEXT,
    conclusion TEXT,
    head_sha TEXT,
    diagnosis TEXT,
    updated_at TEXT,
    UNIQUE(repo, run_id)
);

CREATE TABLE IF NOT EXISTS notification_cache (
    id TEXT PRIMARY KEY,
    repo TEXT,
    type TEXT,
    title TEXT,
    reason TEXT,
    read INTEGER DEFAULT 0,
    updated_at TEXT
);

-- Copilot context memory (Feature 6)
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge USING fts5(
    content,
    source,
    timestamp,
    tokenize='porter'
);

-- Standup history
CREATE TABLE IF NOT EXISTS standup_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE,
    content TEXT,
    created_at TEXT
);

-- Deploy history
CREATE TABLE IF NOT EXISTS deploy_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT,
    ref TEXT,
    confidence INTEGER,
    risk TEXT,
    run_id INTEGER,
    status TEXT,
    created_at TEXT
);
"""


class Database:
    def __init__(self, config: AppConfig):
        self.config = config
        self.db: aiosqlite.Connection | None = None

    async def initialize(self):
        """Create database and tables."""
        self.db = await aiosqlite.connect(DB_PATH)
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(SCHEMA)
        await self.db.commit()
        log.info("Database initialized at %s", DB_PATH)

    async def close(self):
        if self.db:
            await self.db.close()

    # --- PR Cache ---

    async def upsert_pr(self, repo: str, number: int, **kwargs):
        kwargs["updated_at"] = datetime.utcnow().isoformat()
        cols = ", ".join(["repo", "number"] + list(kwargs.keys()))
        placeholders = ", ".join(["?"] * (2 + len(kwargs)))
        values = [repo, number] + list(kwargs.values())
        conflict_update = ", ".join(f"{k}=excluded.{k}" for k in kwargs)
        await self.db.execute(
            f"INSERT INTO pr_cache ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(repo, number) DO UPDATE SET {conflict_update}",
            values,
        )
        await self.db.commit()

    async def get_pending_prs(self, repos: list[str] | None = None) -> list[dict]:
        query = "SELECT * FROM pr_cache WHERE state = 'open'"
        params = []
        if repos:
            placeholders = ",".join("?" * len(repos))
            query += f" AND repo IN ({placeholders})"
            params = repos
        query += " ORDER BY updated_at DESC"
        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # --- CI Cache ---

    async def upsert_ci_run(self, repo: str, run_id: int, **kwargs):
        kwargs["updated_at"] = datetime.utcnow().isoformat()
        cols = ", ".join(["repo", "run_id"] + list(kwargs.keys()))
        placeholders = ", ".join(["?"] * (2 + len(kwargs)))
        values = [repo, run_id] + list(kwargs.values())
        conflict_update = ", ".join(f"{k}=excluded.{k}" for k in kwargs)
        await self.db.execute(
            f"INSERT INTO ci_cache ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(repo, run_id) DO UPDATE SET {conflict_update}",
            values,
        )
        await self.db.commit()

    async def get_failed_runs(self, repo: str | None = None) -> list[dict]:
        query = "SELECT * FROM ci_cache WHERE conclusion = 'failure'"
        params = []
        if repo:
            query += " AND repo = ?"
            params = [repo]
        query += " ORDER BY updated_at DESC LIMIT 10"
        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # --- Knowledge Base (Context Keeper) ---

    async def save_knowledge(self, content: str, source: str):
        await self.db.execute(
            "INSERT INTO knowledge (content, source, timestamp) VALUES (?, ?, ?)",
            (content, source, datetime.utcnow().isoformat()),
        )
        await self.db.commit()

    async def query_knowledge(self, question: str, limit: int = 5) -> list[dict]:
        async with self.db.execute(
            "SELECT content, source, timestamp FROM knowledge WHERE knowledge MATCH ? ORDER BY rank LIMIT ?",
            (question, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # --- Standup History ---

    async def save_standup(self, date: str, content: str):
        await self.db.execute(
            "INSERT OR REPLACE INTO standup_history (date, content, created_at) VALUES (?, ?, ?)",
            (date, content, datetime.utcnow().isoformat()),
        )
        await self.db.commit()

    async def get_latest_standup(self) -> dict | None:
        async with self.db.execute(
            "SELECT * FROM standup_history ORDER BY date DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    # --- Deploy History ---

    async def save_deploy(self, repo: str, ref: str, confidence: int, risk: str,
                          run_id: int | None = None, status: str = "pending"):
        await self.db.execute(
            "INSERT INTO deploy_history (repo, ref, confidence, risk, run_id, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (repo, ref, confidence, risk, run_id, status, datetime.utcnow().isoformat()),
        )
        await self.db.commit()
