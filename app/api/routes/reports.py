from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import WorkspaceContext, workspace_context
from app.database import get_db
from app.models import Experiment, Report
from app.services.audit_service import audit
from app.services.report_service import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/experiments/{experiment_id}", status_code=201)
def generate_report(
    experiment_id: uuid.UUID,
    format: str = "pdf",
    currency: str = "PLN",
    context: WorkspaceContext = Depends(workspace_context),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    experiment = db.get(Experiment, experiment_id)
    if not experiment or experiment.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Experiment not found")
    try:
        report = report_service.generate(db, experiment_id, context.user.id, format, currency)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit(db, context.workspace.id, context.user.id, "report.generated", "report", report.id)
    db.commit()
    return {"id": report.id, "format": report.format, "checksum": report.checksum}


@router.get("/{report_id}/download")
def download_report(
    report_id: uuid.UUID,
    context: WorkspaceContext = Depends(workspace_context),
    db: Session = Depends(get_db),
) -> FileResponse:
    report = db.scalar(
        select(Report)
        .join(Experiment)
        .where(Report.id == report_id, Experiment.workspace_id == context.workspace.id)
    )
    if not report or not Path(report.file_path).is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(report.file_path, filename=f"evalforge-report.{report.format}")
