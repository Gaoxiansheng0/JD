from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from resumefit.projects import FactNotConfirmable, ProjectService
from resumefit.routers.deps import project_service

router = APIRouter(tags=["projects"])


class ProjectIn(BaseModel):
    name: str = Field(min_length=1)
    company: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)


class FactIn(BaseModel):
    text: str = Field(min_length=1)
    source: str = ""
    status: str = "pending"


class StatusIn(BaseModel):
    status: str


class ImportIn(BaseModel):
    name: str = Field(min_length=1)
    company: str = ""
    text: str = Field(min_length=1)
    original_name: str = ""


@router.post("/projects/import", status_code=201)
def import_material(
    payload: ImportIn, service: ProjectService = Depends(project_service)
) -> dict[str, Any]:
    result = service.import_material(payload.model_dump())
    return {
        "project": asdict(result["project"]),
        "source_id": result["source_id"],
        "facts": [asdict(fact) for fact in result["facts"]],
    }


@router.get("/projects/search")
def search_facts(q: str, service: ProjectService = Depends(project_service)) -> list[dict[str, Any]]:
    return [asdict(fact) for fact in service.search_confirmed_facts(q)]


@router.get("/projects")
def list_projects(service: ProjectService = Depends(project_service)) -> list[dict[str, Any]]:
    return [asdict(project) for project in service.list_projects()]


@router.post("/projects", status_code=201)
def create_project(
    payload: ProjectIn, service: ProjectService = Depends(project_service)
) -> dict[str, Any]:
    return asdict(service.create_project(payload.model_dump()))


@router.get("/projects/{project_id}")
def read_project(
    project_id: str, service: ProjectService = Depends(project_service)
) -> dict[str, Any]:
    project = service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {**asdict(project), "facts": [asdict(f) for f in service.list_facts(project_id)]}


@router.post("/projects/{project_id}/facts", status_code=201)
def add_fact(
    project_id: str, payload: FactIn, service: ProjectService = Depends(project_service)
) -> dict[str, Any]:
    if service.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return asdict(service.add_fact(project_id, payload.model_dump()))


@router.post("/facts/{fact_id}/confirm")
def confirm_fact(fact_id: str, service: ProjectService = Depends(project_service)) -> dict[str, Any]:
    try:
        return asdict(service.confirm_fact(fact_id))
    except FactNotConfirmable as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/facts/{fact_id}/status")
def set_fact_status(
    fact_id: str, payload: StatusIn, service: ProjectService = Depends(project_service)
) -> dict[str, Any]:
    try:
        return asdict(service.set_fact_status(fact_id, payload.status))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
