"""
storage.py — Lightweight SQLite storage for job deduplication and history tracking.

Tracks which jobs have been seen before, marks new ones, and provides
query methods for history analysis.

Uses Python's built-in sqlite3 — zero additional dependencies.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = "data/jobs.db"


def _get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get a SQLite connection, creating the DB and table if needed."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT UNIQUE NOT NULL,
            source_platform TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            salary TEXT,
            tags TEXT,               -- JSON array
            posted_at TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            is_new INTEGER DEFAULT 1  -- 1 = first time seen this run
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_platform ON jobs(source_platform)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_at)
    """)
    conn.commit()
    return conn


def upsert_jobs(jobs: list[Any], db_path: str = DB_PATH) -> dict[str, int]:
    """Insert new jobs and update last_seen_at for existing ones.

    Returns:
        {"new": int, "existing": int, "total": int}
    """
    conn = _get_conn(db_path)
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0
    existing_count = 0

    try:
        # Reset is_new flag for all existing records
        conn.execute("UPDATE jobs SET is_new = 0")

        for job in jobs:
            source_url = getattr(job, "source_url", "")
            tags = getattr(job, "tags", [])
            clean_tags = [t for t in tags if not t.startswith("telegram:")]

            try:
                conn.execute(
                """
                INSERT INTO jobs (
                    source_url, source_platform, title, company,
                    location, salary, tags, posted_at,
                    first_seen_at, last_seen_at, is_new
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    source_url,
                    getattr(job, "source_platform", ""),
                    getattr(job, "raw_title", ""),
                    getattr(job, "raw_company_name", ""),
                    getattr(job, "raw_location_text", ""),
                    getattr(job, "raw_salary_text", ""),
                    json.dumps(clean_tags),
                    getattr(job, "raw_posted_at_text", ""),
                    now,
                    now,
                ),
                )
                new_count += 1
            except sqlite3.IntegrityError:
                # Already exists — update last_seen_at
                conn.execute(
                    "UPDATE jobs SET last_seen_at = ? WHERE source_url = ?",
                    (now, source_url),
                )
                existing_count += 1

        conn.commit()
    finally:
        conn.close()

    return {
        "new": new_count,
        "existing": existing_count,
        "total": new_count + existing_count,
    }


def get_new_jobs(db_path: str = DB_PATH) -> list[dict]:
    """Return jobs marked as new (first seen this run)."""
    conn = _get_conn(db_path)
    cursor = conn.execute(
        "SELECT * FROM jobs WHERE is_new = 1 ORDER BY id DESC"
    )
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_all_jobs(db_path: str = DB_PATH) -> list[dict]:
    """Return all jobs in the database."""
    conn = _get_conn(db_path)
    cursor = conn.execute("SELECT * FROM jobs ORDER BY first_seen_at DESC")
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_stats(db_path: str = DB_PATH) -> dict[str, Any]:
    """Return summary statistics about the job database."""
    conn = _get_conn(db_path)

    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    new = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_new = 1").fetchone()[0]
    by_platform = dict(
        conn.execute(
            "SELECT source_platform, COUNT(*) FROM jobs GROUP BY source_platform"
        ).fetchall()
    )

    conn.close()
    return {"total": total, "new_this_run": new, "by_platform": by_platform}
