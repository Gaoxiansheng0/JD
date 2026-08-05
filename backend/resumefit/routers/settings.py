from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from resumefit.privacy import Redactor
from resumefit.settings import ModelNotConfigured, SettingsService

router = APIRouter(tags=["settings"])


def settings_service(request: Request) -> SettingsService:
    return SettingsService(request.app.state.db, request.app.state.keychain)


class ModelSettingsIn(BaseModel):
    api_base_url: str = ""
    text_model: str = ""
    api_key: str | None = None
    timeout_seconds: int = 120
    redaction_terms: list[str] = []


class RedactionPreviewIn(BaseModel):
    text: str
    terms: list[str] = []


@router.get("/settings/model")
def read_model_settings(service: SettingsService = Depends(settings_service)) -> dict[str, Any]:
    return service.get()


@router.put("/settings/model")
def save_model_settings(
    payload: ModelSettingsIn, service: SettingsService = Depends(settings_service)
) -> dict[str, Any]:
    return service.save(payload.model_dump())


@router.post("/settings/model/test")
def test_model_settings(service: SettingsService = Depends(settings_service)) -> dict[str, Any]:
    """能力探测：连通 → 鉴权 → 结构化 JSON（规格 §13.2）。用户明确点击才会发起。"""
    from pydantic import BaseModel as ProbeBase

    class Probe(ProbeBase):
        ok: bool

    try:
        client = service.model_client()
    except ModelNotConfigured as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    try:
        client.complete_json(
            "capability-probe",
            [{"role": "user", "content": '只回复 JSON：{"ok": true}'}],
            Probe,
        )
    except Exception as error:  # 探测失败要把原因显示出来，而不是静默通过
        return {"structured_output": False, "detail": str(error)}
    return {"structured_output": True, "detail": "接口连通，且支持结构化 JSON 输出"}


@router.post("/settings/redaction/preview")
def preview_redaction(payload: RedactionPreviewIn) -> dict[str, Any]:
    redacted = Redactor().apply(payload.text, payload.terms)
    # 只回传脱敏后的文本，映射表留在本地。
    return {"text": redacted.text, "token_count": len(redacted.mapping)}
