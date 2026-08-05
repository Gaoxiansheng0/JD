"""FastAPI 应用工厂。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from resumefit.config import AppConfig
from resumefit.db import Database
from resumefit.privacy import InMemoryKeychain, KeychainStore
from resumefit.routers import profile, projects, records, settings, workflow


def create_app(data_root: Path | None = None, keychain: object | None = None) -> FastAPI:
    config = AppConfig.for_root(data_root) if data_root else AppConfig.default()
    db = Database(config)
    db.initialize()

    app = FastAPI(title="Resume Fit")
    app.state.config = config
    app.state.db = db
    # 显式传入数据根目录的场景（测试、临时工作区）不去碰真实钥匙串。
    app.state.keychain = keychain or (InMemoryKeychain() if data_root else KeychainStore())

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(profile.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(records.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    app.include_router(workflow.router, prefix="/api")

    # 构建过前端就直接托管它；开发时走 Vite，这里没有 dist 也不影响 API。
    # 必须在所有 /api 路由之后挂载，否则根路径会吃掉 API 请求。
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="ui")

    return app
