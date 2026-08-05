"""模型接入配置。API Key 只进钥匙串，数据库里只留账户引用（规格 §13.1）。"""

from __future__ import annotations

import json
from typing import Any

from resumefit.db import LOCAL_WORKSPACE_ID, Database, utc_now
from resumefit.models import ModelCallLog, ModelClient

KEYCHAIN_SERVICE = "Resume Fit"


class ModelNotConfigured(Exception):
    """还没有配置接口地址、模型名称或 API Key。"""


class SettingsService:
    def __init__(self, db: Database, keychain: Any, workspace_id: str = LOCAL_WORKSPACE_ID) -> None:
        self.db = db
        self.keychain = keychain
        self.workspace_id = workspace_id

    def get(self) -> dict[str, Any]:
        row = self.db.fetchone(
            "SELECT api_base_url, text_model, keychain_account, timeout_seconds, redaction_terms"
            " FROM settings WHERE workspace_id = ?",
            (self.workspace_id,),
        )
        if row is None:
            return {
                "api_base_url": "",
                "text_model": "",
                "timeout_seconds": 120,
                "redaction_terms": [],
                "has_api_key": False,
            }
        return {
            "api_base_url": row["api_base_url"],
            "text_model": row["text_model"],
            "timeout_seconds": row["timeout_seconds"],
            "redaction_terms": json.loads(row["redaction_terms"]),
            # 保存后不再回显密钥本身，只回显「已配置」。
            "has_api_key": self.keychain.get(KEYCHAIN_SERVICE, row["keychain_account"]) is not None,
        }

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        account = payload.get("keychain_account", "default")
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO settings (workspace_id, api_base_url, text_model, keychain_account,"
                " timeout_seconds, redaction_terms, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(workspace_id) DO UPDATE SET"
                " api_base_url = excluded.api_base_url, text_model = excluded.text_model,"
                " keychain_account = excluded.keychain_account,"
                " timeout_seconds = excluded.timeout_seconds,"
                " redaction_terms = excluded.redaction_terms, updated_at = excluded.updated_at",
                (
                    self.workspace_id,
                    payload.get("api_base_url", ""),
                    payload.get("text_model", ""),
                    account,
                    payload.get("timeout_seconds", 120),
                    json.dumps(payload.get("redaction_terms", []), ensure_ascii=False),
                    utc_now(),
                ),
            )
        if payload.get("api_key"):
            self.keychain.set(KEYCHAIN_SERVICE, account, payload["api_key"])
        return self.get()

    def model_client(self) -> ModelClient:
        row = self.db.fetchone(
            "SELECT api_base_url, text_model, keychain_account, timeout_seconds"
            " FROM settings WHERE workspace_id = ?",
            (self.workspace_id,),
        )
        if row is None or not row["api_base_url"] or not row["text_model"]:
            raise ModelNotConfigured("请先在设置里填写接口地址和模型名称")

        api_key = self.keychain.get(KEYCHAIN_SERVICE, row["keychain_account"])
        if not api_key:
            raise ModelNotConfigured("请先在设置里填写 API Key")

        return ModelClient(
            endpoint=row["api_base_url"],
            api_key=api_key,
            model=row["text_model"],
            timeout=row["timeout_seconds"],
            log=ModelCallLog(self.db, self.workspace_id),
        )
