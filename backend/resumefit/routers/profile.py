from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from resumefit.documents import extract_document
from resumefit.projects import ProjectService
from resumefit.routers.deps import project_service
from resumefit.storage import LocalStorage, UnsupportedUpload

router = APIRouter(tags=["profile"])


class MasterResumeIn(BaseModel):
    text: str = Field(min_length=1)
    original_name: str = ""


class ResumeIn(BaseModel):
    text: str = Field(min_length=1)
    label: str = ""
    original_name: str = "粘贴的简历"


@router.get("/resumes")
def list_resumes(service: ProjectService = Depends(project_service)) -> list[dict[str, Any]]:
    return service.list_resumes()


@router.post("/resumes", status_code=201)
def save_resume(
    payload: ResumeIn, service: ProjectService = Depends(project_service)
) -> dict[str, Any]:
    return service.save_resume(payload.model_dump())


@router.post("/resumes/upload", status_code=201)
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    label: str = Form(""),
    service: ProjectService = Depends(project_service),
) -> dict[str, Any]:
    """上传 TXT / DOCX / 文本型 PDF。扫描 PDF 明确报错，不返回空内容。"""
    storage = LocalStorage(request.app.state.config)
    try:
        stored = storage.save_upload(file.file, file.filename or "简历", "imports")
    except UnsupportedUpload as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    extracted = extract_document(stored.path, file.content_type or "")
    if extracted.status != "success":
        raise HTTPException(
            status_code=422,
            detail=extracted.warnings[0] if extracted.warnings else "无法从这个文件提取文本",
        )

    return service.save_resume(
        {
            "text": extracted.text,
            "label": label or stored.original_name,
            "original_name": stored.original_name,
            "stored_path": str(stored.path),
            "pages": extracted.pages,
            "warnings": extracted.warnings,
        }
    )


@router.get("/resumes/{source_id}")
def read_resume(
    source_id: str, service: ProjectService = Depends(project_service)
) -> dict[str, Any]:
    source = service.get_source(source_id)
    if source is None or source["kind"] != "resume":
        raise HTTPException(status_code=404, detail="简历不存在")
    return source


@router.get("/profile/master-resume")
def read_master_resume(service: ProjectService = Depends(project_service)) -> dict[str, Any]:
    return service.get_master_resume()


@router.post("/profile/master-resume")
def save_master_resume(
    payload: MasterResumeIn, service: ProjectService = Depends(project_service)
) -> dict[str, Any]:
    return service.save_master_resume(payload.model_dump())


@router.get("/profile")
def read_profile(service: ProjectService = Depends(project_service)) -> dict[str, Any]:
    return service.get_profile()


@router.put("/profile")
def save_profile(
    payload: dict[str, Any], service: ProjectService = Depends(project_service)
) -> dict[str, Any]:
    return service.save_profile(payload)
