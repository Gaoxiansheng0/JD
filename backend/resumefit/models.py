"""OpenAI 兼容的结构化模型调用。

规格 §13.3：模型返回 → JSON 解析 → Schema 校验 → 允许一次定向修复 → 仍失败则停止。
不合法输出不能强行进入后续流程，也不自动切换到别的供应商。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Callable, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from resumefit.db import LOCAL_WORKSPACE_ID, Database

T = TypeVar("T", bound=BaseModel)

Transport = Callable[[dict[str, Any]], dict[str, Any]]

REPAIR_PROMPT = (
    "上一次回复不是符合要求的 JSON。请只输出一个合法的 JSON 对象，"
    "严格匹配以下 JSON Schema，不要包含解释文字或 Markdown 代码块。\nSchema：\n{schema}\n错误：\n{error}"
)


class InvalidStructuredResponse(Exception):
    """模型两次都没有返回符合 Schema 的 JSON。"""


class ModelCallLog:
    """调用记录：只存用量和输入摘要哈希，不存 API Key，也不存提示词正文（规格 §13.4）。"""

    def __init__(self, db: Database, workspace_id: str = LOCAL_WORKSPACE_ID) -> None:
        self.db = db
        self.workspace_id = workspace_id

    def record(
        self,
        *,
        model: str,
        task: str,
        input_digest: str,
        usage: dict[str, Any],
        status: str,
        attempts: int,
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO model_call_records"
                " (id, workspace_id, model, task, input_digest, prompt_tokens, completion_tokens,"
                "  status, attempts)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    self.workspace_id,
                    model,
                    task,
                    input_digest,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                    status,
                    attempts,
                ),
            )


class ModelClient:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str = "",
        timeout: float = 120.0,
        transport: Transport | None = None,
        log: ModelCallLog | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.transport = transport or self._http_transport
        self.log = log

    def _http_transport(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.endpoint}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def complete_json(self, task: str, messages: list[dict[str, str]], schema: type[T]) -> T:
        json_schema = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        digest = hashlib.sha256(
            json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()

        attempt_messages = list(messages)
        usage: dict[str, Any] = {}
        last_error = ""

        for attempt in (1, 2):
            payload = {
                "model": self.model,
                "messages": attempt_messages,
                "response_format": {"type": "json_object"},
            }
            response = self.transport(payload)
            usage = response.get("usage", {}) or {}
            content = response["choices"][0]["message"]["content"]

            try:
                parsed = schema.model_validate_json(content)
            except (ValidationError, ValueError) as error:
                last_error = str(error)
                if attempt == 2:
                    break
                # 一次定向修复：把原始回复和错误一起回传，不重新构造整轮对话。
                attempt_messages = [
                    *messages,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": REPAIR_PROMPT.format(schema=json_schema, error=last_error),
                    },
                ]
                continue

            self._record(task, digest, usage, "succeeded", attempt)
            return parsed

        self._record(task, digest, usage, "invalid_json", 2)
        raise InvalidStructuredResponse(f"模型两次都未返回符合 Schema 的 JSON：{last_error}")

    def _record(self, task: str, digest: str, usage: dict[str, Any], status: str, attempts: int) -> None:
        if self.log is not None:
            self.log.record(
                model=self.model,
                task=task,
                input_digest=digest,
                usage=usage,
                status=status,
                attempts=attempts,
            )
