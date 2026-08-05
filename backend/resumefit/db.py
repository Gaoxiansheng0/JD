"""SQLite 连接、前向迁移与事务。"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from resumefit.config import AppConfig

LOCAL_WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"

# 前向迁移。每个任务按需追加一条，不预先为未实现的功能建表。
# 中文全文检索用 trigram 分词器：unicode61 不切分中文，`测试集` 匹配不到「建立 200 条测试集」。
MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        f"""
        CREATE TABLE workspaces (
            id          TEXT PRIMARY KEY,
            slug        TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE profiles (
            workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
            payload      TEXT NOT NULL DEFAULT '{{}}',
            updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE projects (
            id           TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name         TEXT NOT NULL,
            company      TEXT NOT NULL DEFAULT '',
            detail       TEXT NOT NULL DEFAULT '{{}}',
            archived     INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE atomic_facts (
            id           TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id   TEXT REFERENCES projects(id) ON DELETE CASCADE,
            text         TEXT NOT NULL,
            source       TEXT NOT NULL DEFAULT '',
            metric_key   TEXT NOT NULL DEFAULT '',
            status       TEXT NOT NULL DEFAULT 'pending',
            confirmed_at TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX idx_facts_project ON atomic_facts(project_id);

        CREATE VIRTUAL TABLE fact_search USING fts5(
            body, fact_id UNINDEXED, tokenize='trigram'
        );

        INSERT INTO workspaces (id, slug, name, created_at)
        VALUES ('{LOCAL_WORKSPACE_ID}', 'local', '本地工作区', datetime('now'));
        """,
    ),
    (
        2,
        """
        CREATE TABLE imported_sources (
            id            TEXT PRIMARY KEY,
            workspace_id  TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            kind          TEXT NOT NULL,
            original_name TEXT NOT NULL DEFAULT '',
            stored_path   TEXT NOT NULL DEFAULT '',
            text          TEXT NOT NULL DEFAULT '',
            pages         INTEGER NOT NULL DEFAULT 0,
            status        TEXT NOT NULL DEFAULT 'success',
            warnings      TEXT NOT NULL DEFAULT '[]',
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        ALTER TABLE profiles ADD COLUMN master_resume_text TEXT NOT NULL DEFAULT '';
        ALTER TABLE profiles ADD COLUMN master_resume_source_id TEXT;

        ALTER TABLE atomic_facts ADD COLUMN source_id TEXT;
        ALTER TABLE atomic_facts ADD COLUMN offset_start INTEGER;
        ALTER TABLE atomic_facts ADD COLUMN offset_end INTEGER;
        """,
    ),
    (
        3,
        """
        CREATE TABLE generation_records (
            id             TEXT PRIMARY KEY,
            workspace_id   TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            title          TEXT NOT NULL DEFAULT '',
            company        TEXT NOT NULL DEFAULT '',
            jd_text        TEXT NOT NULL DEFAULT '',
            jd_version     INTEGER NOT NULL DEFAULT 0,
            workflow_state TEXT NOT NULL DEFAULT 'DRAFT',
            archived       INTEGER NOT NULL DEFAULT 0,
            created_at     TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """,
    ),
    (
        4,
        """
        CREATE TABLE settings (
            workspace_id     TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
            api_base_url     TEXT NOT NULL DEFAULT '',
            text_model       TEXT NOT NULL DEFAULT '',
            keychain_account TEXT NOT NULL DEFAULT 'default',
            timeout_seconds  INTEGER NOT NULL DEFAULT 120,
            redaction_terms  TEXT NOT NULL DEFAULT '[]',
            updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- 只记录用量与输入摘要哈希；不存 API Key，也不存提示词正文（规格 §13.4）。
        CREATE TABLE model_call_records (
            id                TEXT PRIMARY KEY,
            workspace_id      TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            model             TEXT NOT NULL DEFAULT '',
            task              TEXT NOT NULL DEFAULT '',
            input_digest      TEXT NOT NULL DEFAULT '',
            prompt_tokens     INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            status            TEXT NOT NULL DEFAULT '',
            attempts          INTEGER NOT NULL DEFAULT 1,
            created_at        TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """,
    ),
    (
        5,
        """
        -- 岗位洞察和匹配报告：每条记录各留一份最新的，jd_version 决定是否过期。
        CREATE TABLE artifacts (
            id         TEXT PRIMARY KEY,
            record_id  TEXT NOT NULL REFERENCES generation_records(id) ON DELETE CASCADE,
            kind       TEXT NOT NULL,
            jd_version INTEGER NOT NULL,
            payload    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(record_id, kind)
        );

        -- 简历版本不可覆盖：每次完整生成都新增一条（规格 §10.8）。
        CREATE TABLE resume_versions (
            id             TEXT PRIMARY KEY,
            record_id      TEXT NOT NULL REFERENCES generation_records(id) ON DELETE CASCADE,
            version_number INTEGER NOT NULL,
            jd_version     INTEGER NOT NULL,
            label          TEXT NOT NULL DEFAULT '',
            strategy       TEXT NOT NULL DEFAULT '{}',
            document       TEXT NOT NULL,
            blocked        TEXT NOT NULL DEFAULT '[]',
            validation     TEXT NOT NULL DEFAULT '[]',
            prompt_version TEXT NOT NULL DEFAULT '',
            is_final       INTEGER NOT NULL DEFAULT 0,
            created_at     TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(record_id, version_number)
        );
        """,
    ),
    (
        6,
        """
        -- 简历库：一次分析要明确用哪一份简历，而不是隐式取最新的。
        ALTER TABLE imported_sources ADD COLUMN label TEXT NOT NULL DEFAULT '';
        ALTER TABLE generation_records ADD COLUMN resume_source_id TEXT;
        CREATE INDEX idx_sources_kind ON imported_sources(workspace_id, kind);
        """,
    ),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._local = threading.local()

    @property
    def connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.config.database_path, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn = conn
        return conn

    def initialize(self) -> None:
        conn = self.connection
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            " version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {row["version"] for row in conn.execute("SELECT version FROM schema_version")}
        for version, script in MIGRATIONS:
            if version in applied:
                continue
            # executescript 自带隐式提交，不能包在 transaction() 里。
            conn.executescript(script)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, utc_now()),
            )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connection
        conn.execute("BEGIN")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        return self.connection.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return self.connection.execute(sql, params).fetchall()
