import json

import pytest
from pydantic import BaseModel

from resumefit.models import InvalidStructuredResponse, ModelClient
from resumefit.privacy import InMemoryKeychain, Redactor


class InsightProbe(BaseModel):
    title: str


def transport_returning(*contents: str):
    """按顺序返回预设内容的假传输层，并记录收到的请求。"""
    calls: list[dict] = []
    queue = list(contents)

    def _transport(payload: dict) -> dict:
        calls.append(payload)
        content = queue.pop(0) if queue else contents[-1]
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

    _transport.calls = calls  # type: ignore[attr-defined]
    return _transport


def make_client(transport):
    return ModelClient(
        endpoint="https://model.example/v1", api_key="key", model="probe-model", transport=transport
    )


# ---- 脱敏 ----


def test_redactor_replaces_sensitive_values_with_stable_local_tokens():
    redacted = Redactor().apply("服务于星河银行，转化率 11.6%", ["星河银行", "11.6%"])

    # 只替换选中的字面值本身，不动周围空白。
    assert redacted.text == "服务于[敏感1]，转化率 [敏感2]"
    assert redacted.mapping == {"[敏感1]": "星河银行", "[敏感2]": "11.6%"}


def test_redactor_replaces_longer_terms_first_so_they_are_not_broken_up():
    redacted = Redactor().apply("星河银行信用卡中心的项目", ["星河银行", "星河银行信用卡中心"])

    assert "星河银行信用卡中心" not in redacted.text
    assert redacted.text == "[敏感2]的项目"


def test_restore_puts_the_original_values_back():
    redactor = Redactor()
    redacted = redactor.apply("服务于星河银行", ["星河银行"])

    assert redactor.restore(redacted.text, redacted.mapping) == "服务于星河银行"


# ---- 密钥 ----


def test_keychain_round_trips_and_never_returns_a_missing_secret():
    keychain = InMemoryKeychain()
    keychain.set("Resume Fit", "default", "super-secret")

    assert keychain.get("Resume Fit", "default") == "super-secret"
    assert keychain.get("Resume Fit", "other") is None


# ---- 结构化调用 ----


def test_model_client_returns_a_validated_object():
    client = make_client(transport_returning(json.dumps({"title": "AI 产品经理"})))

    assert client.complete_json("probe", [], InsightProbe).title == "AI 产品经理"


def test_model_client_repairs_once_then_succeeds():
    transport = transport_returning('{"wrong": 1}', json.dumps({"title": "AI 产品经理"}))

    result = make_client(transport).complete_json("probe", [], InsightProbe)

    assert result.title == "AI 产品经理"
    assert len(transport.calls) == 2


def test_model_client_rejects_response_that_does_not_match_schema():
    transport = transport_returning('{"wrong": 1}')

    with pytest.raises(InvalidStructuredResponse):
        make_client(transport).complete_json("probe", [], InsightProbe)

    # 一次定向修复后就停止，不会无限重试产生额外费用。
    assert len(transport.calls) == 2


def test_model_client_rejects_unparseable_json():
    with pytest.raises(InvalidStructuredResponse):
        make_client(transport_returning("这不是 JSON")).complete_json("probe", [], InsightProbe)


def test_call_record_stores_usage_but_never_the_api_key_or_prompt_body(db):
    from resumefit.models import ModelCallLog

    log = ModelCallLog(db)
    client = make_client(transport_returning(json.dumps({"title": "AI 产品经理"})))
    client.log = log

    client.complete_json("probe", [{"role": "user", "content": "简历全文：张三……"}], InsightProbe)

    row = db.fetchone("SELECT * FROM model_call_records")
    assert row["task"] == "probe"
    assert row["completion_tokens"] == 5
    stored = " ".join(str(value) for value in tuple(row))
    assert "key" not in stored and "张三" not in stored


def test_saved_api_key_is_never_returned_to_the_client(client):
    client.put(
        "/api/settings/model",
        json={
            "api_base_url": "https://model.example/v1",
            "text_model": "probe-model",
            "api_key": "super-secret",
        },
    )

    body = client.get("/api/settings/model").json()

    assert body["has_api_key"] is True
    assert "super-secret" not in str(body)


def test_model_test_endpoint_refuses_when_nothing_is_configured(client):
    assert client.post("/api/settings/model/test").status_code == 400
