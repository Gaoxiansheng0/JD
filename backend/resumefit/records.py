"""历史生成记录与 JD 确认。

`jd_version` 是下游依赖的唯一凭据：岗位洞察、匹配报告和简历版本各自记录
生成时的 jd_version，比对不上就是过期。改 JD 会让记录退回 DRAFT，必须重新确认。
这些是内部依赖状态，不是投递状态（规格 §14）。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from resumefit.db import LOCAL_WORKSPACE_ID, Database, utc_now

COLUMNS = "id, title, company, jd_text, jd_version, workflow_state, resume_source_id"


class JDNotConfirmable(Exception):
    """当前 JD 内容不足以确认。"""


def derive_title(jd_text: str) -> str:
    """从 JD 里取一个能认出来的标题：优先「岗位/职位」那一行，否则用第一行。"""
    lines = [line.strip() for line in jd_text.splitlines() if line.strip()]
    for line in lines:
        for marker in ("岗位：", "岗位:", "职位：", "职位:", "招聘："):
            if marker in line:
                title = line.split(marker, 1)[1].strip()
                if title:
                    return title[:40]
    return lines[0][:40] if lines else "未命名岗位"


@dataclass(frozen=True)
class GenerationRecord:
    id: str
    title: str
    company: str
    jd_text: str
    jd_version: int
    workflow_state: str
    resume_source_id: str | None = None


class RecordService:
    def __init__(self, db: Database, workspace_id: str = LOCAL_WORKSPACE_ID) -> None:
        self.db = db
        self.workspace_id = workspace_id

    def create(self, payload: dict[str, Any]) -> GenerationRecord:
        record_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO generation_records (id, workspace_id, title, company)"
                " VALUES (?, ?, ?, ?)",
                (record_id, self.workspace_id, payload.get("title", ""), payload.get("company", "")),
            )
        return self.get(record_id)  # type: ignore[return-value]

    def get(self, record_id: str) -> GenerationRecord | None:
        row = self.db.fetchone(
            f"SELECT {COLUMNS} FROM generation_records WHERE id = ? AND workspace_id = ?",
            (record_id, self.workspace_id),
        )
        return GenerationRecord(**dict(row)) if row else None

    def list(self) -> list[GenerationRecord]:
        rows = self.db.fetchall(
            f"SELECT {COLUMNS} FROM generation_records"
            " WHERE workspace_id = ? AND archived = 0 ORDER BY created_at DESC, rowid DESC",
            (self.workspace_id,),
        )
        return [GenerationRecord(**dict(row)) for row in rows]

    def set_jd(self, record_id: str, text: str) -> GenerationRecord:
        """改 JD 一律退回 DRAFT——已确认的 JD 被改动后，旧的下游产物不再可信。"""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE generation_records SET jd_text = ?, workflow_state = 'DRAFT',"
                " updated_at = ? WHERE id = ? AND workspace_id = ?",
                (text, utc_now(), record_id, self.workspace_id),
            )
        return self.get(record_id)  # type: ignore[return-value]

    def set_resume(self, record_id: str, resume_source_id: str) -> GenerationRecord:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE generation_records SET resume_source_id = ?, updated_at = ?"
                " WHERE id = ? AND workspace_id = ?",
                (resume_source_id, utc_now(), record_id, self.workspace_id),
            )
        return self.get(record_id)  # type: ignore[return-value]

    def history(self) -> list[dict[str, Any]]:
        """分析记录列表：每条记录已经产出了什么，以及是否还基于当前 JD。"""
        rows = self.db.fetchall(
            """
            SELECT r.id, r.title, r.company, r.jd_version, r.workflow_state, r.created_at,
                   substr(r.jd_text, 1, 120) AS jd_excerpt,
                   s.label AS resume_label,
                   (SELECT payload FROM artifacts a
                     WHERE a.record_id = r.id AND a.kind = 'match'
                       AND a.jd_version = r.jd_version) AS match_payload,
                   EXISTS(SELECT 1 FROM artifacts a
                           WHERE a.record_id = r.id AND a.kind = 'insight') AS has_insight,
                   (SELECT COUNT(*) FROM resume_versions v WHERE v.record_id = r.id) AS resume_count
            FROM generation_records r
            LEFT JOIN imported_sources s ON s.id = r.resume_source_id
            WHERE r.workspace_id = ? AND r.archived = 0
            ORDER BY r.created_at DESC, r.rowid DESC
            """,
            (self.workspace_id,),
        )

        history = []
        for row in rows:
            item = dict(row)
            payload = item.pop("match_payload")
            report = json.loads(payload)["report"] if payload else None
            item["has_insight"] = bool(item["has_insight"])
            # 只做过岗位解读的记录不该显示「尚未分析匹配度」—— 它本来就没打算算。
            item["kind"] = (
                "insight"
                if item["has_insight"] and not payload and not item["resume_label"]
                else "match"
            )
            item["scores"] = (
                {
                    "capability_low": report["capability_low"],
                    "capability_high": report["capability_high"],
                    "presentation_low": report["presentation_low"],
                    "presentation_high": report["presentation_high"],
                    "hard_gate_count": len(report["hard_gate_risks"]),
                }
                if report
                else None
            )
            history.append(item)
        return history

    def confirm_jd(self, record_id: str) -> GenerationRecord:
        record = self.get(record_id)
        if record is None:
            raise JDNotConfirmable("记录不存在")
        if not record.jd_text.strip():
            raise JDNotConfirmable("JD 内容为空，无法确认")

        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE generation_records SET workflow_state = 'JD_CONFIRMED',"
                " jd_version = jd_version + 1, title = ?, updated_at = ? WHERE id = ?",
                (record.title or derive_title(record.jd_text), utc_now(), record_id),
            )
        return self.get(record_id)  # type: ignore[return-value]
