from __future__ import annotations

import csv
import io
import json
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import (
    WorkspaceContext,
    require_roles,
    require_writable,
    workspace_context,
)
from app.config import settings
from app.database import get_db
from app.models import Dataset, DatasetVersion, TestCase
from app.models.entities import Role
from app.schemas.dataset import DatasetCreate, DatasetVersionCreate, TestCaseInput
from app.services.audit_service import audit
from app.services.import_service import import_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _variables(cases: list[TestCaseInput]) -> list[str]:
    return sorted({key for case in cases for key in case.inputs})


def _add_cases(db: Session, version: DatasetVersion, cases: list[TestCaseInput]) -> None:
    for case in cases:
        db.add(
            TestCase(
                dataset_version_id=version.id,
                name=case.name,
                inputs=case.inputs,
                expected_output=case.expected_output,
                expected_keywords=case.expected_keywords,
                reference_context=case.reference_context,
                extra_metadata=case.metadata,
                difficulty=case.difficulty,
            )
        )


@router.get("")
def list_datasets(
    context: WorkspaceContext = Depends(workspace_context), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    datasets = db.scalars(
        select(Dataset)
        .options(selectinload(Dataset.versions).selectinload(DatasetVersion.test_cases))
        .where(Dataset.workspace_id == context.workspace.id, Dataset.is_archived.is_(False))
        .order_by(Dataset.updated_at.desc())
    )
    return [
        {
            "id": dataset.id,
            "name": dataset.name,
            "description": dataset.description,
            "tags": dataset.tags,
            "latest_version": dataset.versions[-1].version,
            "case_count": len(dataset.versions[-1].test_cases),
            "required_variables": dataset.versions[-1].required_variables,
        }
        for dataset in datasets
        if dataset.versions
    ]


@router.post("", status_code=201, dependencies=[Depends(require_writable)])
def create_dataset(
    payload: DatasetCreate,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    dataset = Dataset(
        workspace_id=context.workspace.id,
        created_by_id=context.user.id,
        name=payload.name,
        description=payload.description,
        tags=payload.tags,
    )
    db.add(dataset)
    db.flush()
    version = DatasetVersion(
        dataset_id=dataset.id,
        version=1,
        required_variables=_variables(payload.test_cases),
        created_by_id=context.user.id,
    )
    db.add(version)
    db.flush()
    _add_cases(db, version, payload.test_cases)
    audit(db, context.workspace.id, context.user.id, "dataset.created", "dataset", dataset.id)
    db.commit()
    return {"id": dataset.id, "version": 1, "case_count": len(payload.test_cases)}


@router.post("/{dataset_id}/versions", status_code=201, dependencies=[Depends(require_writable)])
def create_dataset_version(
    dataset_id: uuid.UUID,
    payload: DatasetVersionCreate,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    dataset = db.get(Dataset, dataset_id)
    if not dataset or dataset.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Dataset not found")
    number = (
        int(
            db.scalar(
                select(func.max(DatasetVersion.version)).where(
                    DatasetVersion.dataset_id == dataset_id
                )
            )
            or 0
        )
        + 1
    )
    version = DatasetVersion(
        dataset_id=dataset_id,
        version=number,
        required_variables=_variables(payload.test_cases),
        change_note=payload.change_note,
        created_by_id=context.user.id,
    )
    db.add(version)
    db.flush()
    _add_cases(db, version, payload.test_cases)
    db.commit()
    return {"id": version.id, "version": number, "case_count": len(payload.test_cases)}


@router.post("/import", status_code=201, dependencies=[Depends(require_writable)])
async def import_dataset(
    name: str,
    file: UploadFile = File(...),
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds configured upload limit")
    try:
        cases = (
            import_service.parse_csv(content)
            if file.filename and file.filename.lower().endswith(".csv")
            else import_service.parse_json(content)
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return create_dataset(DatasetCreate(name=name, test_cases=cases), context, db)


@router.get("/{dataset_id}/export/{format}")
def export_dataset(
    dataset_id: uuid.UUID,
    format: str,
    context: WorkspaceContext = Depends(workspace_context),
    db: Session = Depends(get_db),
) -> Response:
    dataset = db.scalar(
        select(Dataset)
        .options(selectinload(Dataset.versions).selectinload(DatasetVersion.test_cases))
        .where(Dataset.id == dataset_id)
    )
    if not dataset or dataset.workspace_id != context.workspace.id or not dataset.versions:
        raise HTTPException(status_code=404, detail="Dataset not found")
    cases = dataset.versions[-1].test_cases
    rows = [
        {
            "name": case.name,
            "inputs": case.inputs,
            "expected_output": case.expected_output,
            "expected_keywords": case.expected_keywords,
            "reference_context": case.reference_context,
            "metadata": case.extra_metadata,
            "difficulty": case.difficulty,
        }
        for case in cases
    ]
    if format == "json":
        return Response(
            json.dumps({"test_cases": rows}, ensure_ascii=False), media_type="application/json"
        )
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )
        return Response(output.getvalue(), media_type="text/csv")
    raise HTTPException(status_code=400, detail="Supported export formats are json and csv")
