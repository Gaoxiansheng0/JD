from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from resumefit.records import JDNotConfirmable, RecordService

router = APIRouter(tags=["records"])


def record_service(request: Request) -> RecordService:
    return RecordService(request.app.state.db)


class RecordIn(BaseModel):
    title: str = ""
    company: str = ""


class JDIn(BaseModel):
    text: str


class ResumeChoiceIn(BaseModel):
    resume_source_id: str


@router.get("/records")
def list_records(service: RecordService = Depends(record_service)) -> list[dict[str, Any]]:
    return [asdict(record) for record in service.list()]


@router.get("/records/history")
def read_history(service: RecordService = Depends(record_service)) -> list[dict[str, Any]]:
    return service.history()


@router.post("/records", status_code=201)
def create_record(
    payload: RecordIn, service: RecordService = Depends(record_service)
) -> dict[str, Any]:
    return asdict(service.create(payload.model_dump()))


@router.get("/records/{record_id}")
def read_record(record_id: str, service: RecordService = Depends(record_service)) -> dict[str, Any]:
    record = service.get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return asdict(record)


@router.put("/records/{record_id}/jd")
def set_jd(
    record_id: str, payload: JDIn, service: RecordService = Depends(record_service)
) -> dict[str, Any]:
    if service.get(record_id) is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return asdict(service.set_jd(record_id, payload.text))


@router.put("/records/{record_id}/resume")
def set_resume(
    record_id: str, payload: ResumeChoiceIn, service: RecordService = Depends(record_service)
) -> dict[str, Any]:
    if service.get(record_id) is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return asdict(service.set_resume(record_id, payload.resume_source_id))


@router.post("/records/{record_id}/jd/confirm")
def confirm_jd(record_id: str, service: RecordService = Depends(record_service)) -> dict[str, Any]:
    try:
        return asdict(service.confirm_jd(record_id))
    except JDNotConfirmable as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
