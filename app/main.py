from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from nicegui import ui

from app.api.routes import auth, datasets, experiments, models, prompts, providers, reports
from app.config import settings
from app.database import SessionLocal, create_schema
from app.middleware.security import SecurityMiddleware
from app.services.demo_service import seed_demo
from app.ui.pages import register_pages


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_schema()
    with SessionLocal() as db:
        seed_demo(db)
    yield


app = FastAPI(
    title="EvalForge API",
    description="Multi Provider LLM Evaluation Platform",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(SecurityMiddleware, settings=settings)

for router in (
    auth.router,
    providers.router,
    models.router,
    prompts.router,
    datasets.router,
    experiments.router,
    reports.router,
):
    app.include_router(router, prefix="/api")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "evalforge"}


@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse("/ui/welcome")


register_pages()
ui.run_with(
    app,
    mount_path="/ui",
    storage_secret=settings.session_secret,
    title="EvalForge",
    favicon="⚒️",
)


def run() -> None:
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)


if __name__ == "__main__":
    run()
