"""项目经历库：项目、原子事实与确认状态机。

规格 §8.4：事实只能处于 pending / confirmed / rejected / conflict / archived。
只有 confirmed 的事实可以被检索复用，进而用于正式简历。
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from resumefit.db import LOCAL_WORKSPACE_ID, Database, utc_now

STATUSES = ("pending", "confirmed", "rejected", "conflict", "archived")

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


class FactNotConfirmable(Exception):
    """事实处于不能直接确认的状态（例如存在冲突）。"""


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    company: str
    detail: dict[str, Any]


@dataclass(frozen=True)
class AtomicFact:
    id: str
    project_id: str | None
    text: str
    source: str
    status: str
    source_id: str | None = None
    offset_start: int | None = None
    offset_end: int | None = None


FACT_COLUMNS = "id, project_id, text, source, status, source_id, offset_start, offset_end"


def _metric_key(text: str) -> str:
    """把数字抹成 # 得到「同一个说法」的指纹。

    ponytail: 纯字面归一化的朴素启发式，同义改写（「首解率」vs「首次解决率」）识别不出来；
    等真实素材里出现漏检再换成模型判定或指标词表。
    """
    return _NUMBER.sub("#", text).strip()


class ProjectService:
    def __init__(self, db: Database, workspace_id: str = LOCAL_WORKSPACE_ID) -> None:
        self.db = db
        self.workspace_id = workspace_id

    # ---- 项目 ----

    def create_project(self, payload: dict[str, Any]) -> Project:
        project_id = str(uuid.uuid4())
        detail = payload.get("detail") or {}
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, workspace_id, name, company, detail)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    project_id,
                    self.workspace_id,
                    payload["name"],
                    payload.get("company", ""),
                    json.dumps(detail, ensure_ascii=False),
                ),
            )
        return Project(id=project_id, name=payload["name"], company=payload.get("company", ""), detail=detail)

    def list_projects(self) -> list[Project]:
        rows = self.db.fetchall(
            "SELECT id, name, company, detail FROM projects"
            " WHERE workspace_id = ? AND archived = 0 ORDER BY created_at",
            (self.workspace_id,),
        )
        return [
            Project(id=r["id"], name=r["name"], company=r["company"], detail=json.loads(r["detail"]))
            for r in rows
        ]

    def get_project(self, project_id: str) -> Project | None:
        row = self.db.fetchone(
            "SELECT id, name, company, detail FROM projects WHERE id = ? AND workspace_id = ?",
            (project_id, self.workspace_id),
        )
        if row is None:
            return None
        return Project(id=row["id"], name=row["name"], company=row["company"], detail=json.loads(row["detail"]))

    # ---- 原子事实 ----

    def add_fact(self, project_id: str, payload: dict[str, Any]) -> AtomicFact:
        text = payload["text"]
        metric_key = _metric_key(text)
        status = payload.get("status", "pending")
        if status not in STATUSES:
            raise ValueError(f"未知的事实状态：{status}")

        if status != "confirmed" and self._conflicts_with_existing(project_id, text, metric_key):
            status = "conflict"

        fact_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO atomic_facts"
                " (id, workspace_id, project_id, text, source, metric_key, status, confirmed_at,"
                "  source_id, offset_start, offset_end)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fact_id,
                    self.workspace_id,
                    project_id,
                    text,
                    payload.get("source", ""),
                    metric_key,
                    status,
                    utc_now() if status == "confirmed" else None,
                    payload.get("source_id"),
                    payload.get("offset_start"),
                    payload.get("offset_end"),
                ),
            )
            if status == "confirmed":
                self._index(conn, fact_id, text)

        return AtomicFact(
            id=fact_id,
            project_id=project_id,
            text=text,
            source=payload.get("source", ""),
            status=status,
            source_id=payload.get("source_id"),
            offset_start=payload.get("offset_start"),
            offset_end=payload.get("offset_end"),
        )

    def _conflicts_with_existing(self, project_id: str, text: str, metric_key: str) -> bool:
        """同一项目里同一说法给出了不同数字 → 冲突。"""
        numbers = _NUMBER.findall(text)
        if not numbers:
            return False
        rows = self.db.fetchall(
            "SELECT text FROM atomic_facts WHERE project_id = ? AND metric_key = ?"
            " AND status IN ('pending', 'confirmed')",
            (project_id, metric_key),
        )
        return any(_NUMBER.findall(row["text"]) != numbers for row in rows)

    def list_facts(self, project_id: str) -> list[AtomicFact]:
        rows = self.db.fetchall(
            f"SELECT {FACT_COLUMNS} FROM atomic_facts"
            " WHERE project_id = ? AND status != 'archived' ORDER BY created_at",
            (project_id,),
        )
        return [AtomicFact(**dict(row)) for row in rows]

    def confirm_fact(self, fact_id: str) -> AtomicFact:
        row = self.db.fetchone(
            "SELECT status FROM atomic_facts WHERE id = ? AND workspace_id = ?",
            (fact_id, self.workspace_id),
        )
        if row is None:
            raise FactNotConfirmable(f"事实不存在：{fact_id}")
        if row["status"] == "conflict":
            raise FactNotConfirmable("存在冲突的事实必须先编辑或拒绝，不能直接确认")
        return self.set_fact_status(fact_id, "confirmed")

    def set_fact_status(self, fact_id: str, status: str) -> AtomicFact:
        if status not in STATUSES:
            raise ValueError(f"未知的事实状态：{status}")
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE atomic_facts SET status = ?, confirmed_at = ?"
                " WHERE id = ? AND workspace_id = ?",
                (status, utc_now() if status == "confirmed" else None, fact_id, self.workspace_id),
            )
            # 检索索引只保留已确认事实。
            conn.execute("DELETE FROM fact_search WHERE fact_id = ?", (fact_id,))
            if status == "confirmed":
                row = conn.execute("SELECT text FROM atomic_facts WHERE id = ?", (fact_id,)).fetchone()
                self._index(conn, fact_id, row["text"])

        row = self.db.fetchone(
            f"SELECT {FACT_COLUMNS} FROM atomic_facts WHERE id = ?", (fact_id,)
        )
        return AtomicFact(**dict(row))

    @staticmethod
    def _index(conn: Any, fact_id: str, text: str) -> None:
        conn.execute("INSERT INTO fact_search (fact_id, body) VALUES (?, ?)", (fact_id, text))

    def search_confirmed_facts(self, query: str) -> list[AtomicFact]:
        # trigram 分词器要求至少 3 个字符，更短的查询退回普通子串匹配。
        if len(query.strip()) < 3:
            rows = self.db.fetchall(
                f"SELECT {FACT_COLUMNS} FROM atomic_facts"
                " WHERE workspace_id = ? AND status = 'confirmed' AND text LIKE ?"
                " ORDER BY created_at",
                (self.workspace_id, f"%{query.strip()}%"),
            )
        else:
            rows = self.db.fetchall(
                f"SELECT {', '.join('f.' + c for c in FACT_COLUMNS.split(', '))}"
                " FROM fact_search s JOIN atomic_facts f ON f.id = s.fact_id"
                " WHERE fact_search MATCH ? AND f.workspace_id = ? AND f.status = 'confirmed'"
                " ORDER BY rank",
                (query, self.workspace_id),
            )
        return [AtomicFact(**dict(row)) for row in rows]

    # ---- 素材导入 ----

    def save_source(self, payload: dict[str, Any]) -> str:
        source_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO imported_sources"
                " (id, workspace_id, kind, label, original_name, stored_path, text, pages,"
                "  status, warnings)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source_id,
                    self.workspace_id,
                    payload.get("kind", "material"),
                    payload.get("label", ""),
                    payload.get("original_name", ""),
                    payload.get("stored_path", ""),
                    payload.get("text", ""),
                    payload.get("pages", 0),
                    payload.get("status", "success"),
                    json.dumps(payload.get("warnings", []), ensure_ascii=False),
                ),
            )
        return source_id

    # ---- 简历库 ----

    def list_resumes(self) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT id, label, original_name, pages, status, created_at,"
            " length(text) AS char_count FROM imported_sources"
            " WHERE workspace_id = ? AND kind = 'resume' ORDER BY created_at DESC, rowid DESC",
            (self.workspace_id,),
        )
        return [dict(row) for row in rows]

    def save_resume(self, payload: dict[str, Any]) -> dict[str, Any]:
        """存一份简历到简历库。简历文本不会自动变成可复用事实（规格 §8.4）。"""
        source_id = self.save_source(
            {
                "kind": "resume",
                "label": payload.get("label", "") or payload.get("original_name", "未命名简历"),
                "original_name": payload.get("original_name", ""),
                "stored_path": payload.get("stored_path", ""),
                "text": payload["text"],
                "pages": payload.get("pages", 1),
                "status": payload.get("status", "success"),
                "warnings": payload.get("warnings", []),
            }
        )
        return self.get_source(source_id)  # type: ignore[return-value]

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone(
            "SELECT id, kind, label, original_name, text, pages, status, warnings, created_at"
            " FROM imported_sources"
            " WHERE id = ? AND workspace_id = ?",
            (source_id, self.workspace_id),
        )
        if row is None:
            return None
        source = dict(row)
        source["warnings"] = json.loads(source["warnings"])
        return source

    def import_material(self, payload: dict[str, Any]) -> dict[str, Any]:
        """把一段素材拆成项目 + 待确认候选事实。任何一条都不会自动确认。"""
        from resumefit.documents import split_candidate_facts

        text = payload["text"]
        source_id = self.save_source(
            {
                "kind": "material",
                "original_name": payload.get("original_name", ""),
                "stored_path": payload.get("stored_path", ""),
                "text": text,
            }
        )
        project = self.create_project({"name": payload["name"], "company": payload.get("company", "")})
        facts = [
            self.add_fact(
                project.id,
                {
                    "text": candidate.text,
                    "source": payload.get("original_name", "素材导入"),
                    "source_id": source_id,
                    "offset_start": candidate.offset_start,
                    "offset_end": candidate.offset_end,
                },
            )
            for candidate in split_candidate_facts(text)
        ]
        return {"project": project, "source_id": source_id, "facts": facts}

    # ---- 个人档案 ----

    def get_master_resume(self) -> dict[str, Any]:
        row = self.db.fetchone(
            "SELECT master_resume_text, master_resume_source_id FROM profiles WHERE workspace_id = ?",
            (self.workspace_id,),
        )
        if row is None:
            return {"text": "", "source_id": None}
        return {"text": row["master_resume_text"], "source_id": row["master_resume_source_id"]}

    def save_master_resume(self, payload: dict[str, Any]) -> dict[str, Any]:
        """只保存来源和归一化文本，不把简历表述变成可复用事实（规格 §8.4）。"""
        source_id = self.save_source(
            {
                "kind": "resume",
                "original_name": payload.get("original_name", ""),
                "stored_path": payload.get("stored_path", ""),
                "text": payload["text"],
            }
        )
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO profiles (workspace_id, master_resume_text, master_resume_source_id,"
                " updated_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(workspace_id) DO UPDATE SET"
                " master_resume_text = excluded.master_resume_text,"
                " master_resume_source_id = excluded.master_resume_source_id,"
                " updated_at = excluded.updated_at",
                (self.workspace_id, payload["text"], source_id, utc_now()),
            )
        return {"text": payload["text"], "source_id": source_id}

    def get_profile(self) -> dict[str, Any]:
        row = self.db.fetchone(
            "SELECT payload FROM profiles WHERE workspace_id = ?", (self.workspace_id,)
        )
        return json.loads(row["payload"]) if row else {}

    def save_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO profiles (workspace_id, payload, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(workspace_id) DO UPDATE SET payload = excluded.payload,"
                " updated_at = excluded.updated_at",
                (self.workspace_id, json.dumps(payload, ensure_ascii=False), utc_now()),
            )
        return payload
