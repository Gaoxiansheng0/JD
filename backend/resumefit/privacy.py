"""API Key 存放与脱敏。

规格 §16：API Key 只进系统钥匙串，数据库和备份包里只保存引用。
脱敏只替换用户明确选中的字面值，映射表只留在本地。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

SECURITY_BIN = "/usr/bin/security"


@dataclass(frozen=True)
class RedactedText:
    text: str
    mapping: dict[str, str]


class Redactor:
    def apply(self, text: str, terms: list[str]) -> RedactedText:
        """把选中的字面值换成 [敏感N]。编号按传入顺序，替换按长度降序。"""
        tokens = {term: f"[敏感{index}]" for index, term in enumerate(terms, start=1)}
        # 长词先替换，否则 "星河银行信用卡中心" 会被 "星河银行" 拆掉一半。
        for term in sorted(terms, key=len, reverse=True):
            text = text.replace(term, tokens[term])
        return RedactedText(text=text, mapping={token: term for term, token in tokens.items()})

    def restore(self, text: str, mapping: dict[str, str]) -> str:
        for token, original in mapping.items():
            text = text.replace(token, original)
        return text


class InMemoryKeychain:
    """测试用；不落盘。"""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def set(self, service: str, account: str, secret: str) -> None:
        self._store[(service, account)] = secret

    def get(self, service: str, account: str) -> str | None:
        return self._store.get((service, account))

    def delete(self, service: str, account: str) -> None:
        self._store.pop((service, account), None)


class KeychainStore:
    """macOS 钥匙串，通过 /usr/bin/security 调用。"""

    def set(self, service: str, account: str, secret: str) -> None:
        subprocess.run(
            [SECURITY_BIN, "add-generic-password", "-U", "-s", service, "-a", account, "-w", secret],
            check=True,
            capture_output=True,
        )

    def get(self, service: str, account: str) -> str | None:
        result = subprocess.run(
            [SECURITY_BIN, "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def delete(self, service: str, account: str) -> None:
        subprocess.run(
            [SECURITY_BIN, "delete-generic-password", "-s", service, "-a", account],
            capture_output=True,
        )
