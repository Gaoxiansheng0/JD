from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from resumefit.generate import GenerationService
from resumefit.settings import ModelNotConfigured, SettingsService

router = APIRouter(tags=["workflow"])


def generation_service(request: Request) -> GenerationService:
    settings = SettingsService(request.app.state.db, request.app.state.keychain)
    try:
        client = settings.model_client()
    except ModelNotConfigured as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return GenerationService(request.app.state.db, client)


def _run(operation, *args) -> Any:
    try:
        return operation(*args)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/records/{record_id}/insight")
def build_insight(
    record_id: str, service: GenerationService = Depends(generation_service)
) -> dict[str, Any]:
    return _run(service.build_insight, record_id).model_dump()


@router.post("/records/{record_id}/match")
def build_match(
    record_id: str, service: GenerationService = Depends(generation_service)
) -> dict[str, Any]:
    return _run(service.build_match, record_id)


@router.post("/records/{record_id}/resumes")
def build_resume(
    record_id: str, service: GenerationService = Depends(generation_service)
) -> dict[str, Any]:
    return _run(service.build_resume, record_id)


# 读取已有产物不需要模型配置，所以单独用一个轻量依赖。
def artifact_reader(request: Request) -> GenerationService:
    return GenerationService(request.app.state.db, client=None)  # type: ignore[arg-type]


@router.get("/records/{record_id}/insight")
def read_insight(record_id: str, service: GenerationService = Depends(artifact_reader)) -> dict[str, Any]:
    artifact = service.load(record_id, "insight")
    if artifact is None:
        raise HTTPException(status_code=404, detail="尚未生成岗位洞察")
    return artifact


@router.get("/records/{record_id}/match")
def read_match(record_id: str, service: GenerationService = Depends(artifact_reader)) -> dict[str, Any]:
    artifact = service.load(record_id, "match")
    if artifact is None:
        raise HTTPException(status_code=404, detail="尚未生成匹配报告")
    return artifact


@router.get("/records/{record_id}/resumes")
def list_resumes(
    record_id: str, service: GenerationService = Depends(artifact_reader)
) -> list[dict[str, Any]]:
    return service.list_resume_versions(record_id)
