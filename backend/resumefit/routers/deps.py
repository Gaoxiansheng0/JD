from fastapi import Request

from resumefit.projects import ProjectService


def project_service(request: Request) -> ProjectService:
    return ProjectService(request.app.state.db)
