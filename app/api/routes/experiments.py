from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import WorkspaceContext, require_roles, workspace_context
from app.database import get_db
from app.models import Experiment, ExperimentRun, ManualReview
from app.models.entities import ExperimentStatus, Role
from app.schemas.experiment import ExperimentCreate, ManualReviewCreate
from app.services.audit_service import audit
from app.services.experiment_service import experiment_service
from app.services.metrics_service import metrics_service
from app.services.queue_service import QueueUnavailableError, enqueue_experiment
from app.services.recommendation_service import recommendation_service

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("")
def list_experiments(
    context: WorkspaceContext = Depends(workspace_context), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    experiments = db.scalars(
        select(Experiment)
        .where(Experiment.workspace_id == context.workspace.id)
        .order_by(Experiment.created_at.desc())
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "status": item.status,
            "progress": item.progress,
            "total_cost": item.total_cost,
            "currency": item.currency,
            "created_at": item.created_at,
        }
        for item in experiments
    ]


@router.post("", status_code=201)
def create_experiment(
    payload: ExperimentCreate,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        experiment = experiment_service.create(db, context.workspace.id, context.user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit(
        db, context.workspace.id, context.user.id, "experiment.created", "experiment", experiment.id
    )
    db.commit()
    return {"id": experiment.id, "status": experiment.status}


@router.post("/{experiment_id}/run", status_code=202)
def run_experiment(
    experiment_id: uuid.UUID,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    experiment = db.get(Experiment, experiment_id)
    if not experiment or experiment.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Experiment not found")
    try:
        run_count = experiment_service.prepare_runs(db, experiment_id)
        job_id = enqueue_experiment(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except QueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    audit(
        db, context.workspace.id, context.user.id, "experiment.started", "experiment", experiment_id
    )
    db.commit()
    return {"job_id": job_id, "run_count": run_count, "status": "queued"}


@router.post("/{experiment_id}/cancel")
def cancel_experiment(
    experiment_id: uuid.UUID,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    experiment = db.get(Experiment, experiment_id)
    if not experiment or experiment.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if experiment.status not in {
        ExperimentStatus.QUEUED,
        ExperimentStatus.RUNNING,
        ExperimentStatus.PAUSED,
    }:
        raise HTTPException(status_code=409, detail="Experiment cannot be cancelled")
    experiment.status = ExperimentStatus.CANCELLED
    audit(
        db,
        context.workspace.id,
        context.user.id,
        "experiment.cancelled",
        "experiment",
        experiment_id,
    )
    db.commit()
    return {"status": "cancelled"}


@router.get("/{experiment_id}")
def experiment_details(
    experiment_id: uuid.UUID,
    context: WorkspaceContext = Depends(workspace_context),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    experiment = db.scalar(
        select(Experiment)
        .options(selectinload(Experiment.runs).selectinload(ExperimentRun.evaluations))
        .where(Experiment.id == experiment_id)
    )
    if not experiment or experiment.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Experiment not found")
    metrics = metrics_service.aggregate(experiment.runs)
    recommendation = recommendation_service.recommend(
        metrics, experiment.recommendation_weights or {}
    )
    error_rows = db.execute(
        select(ExperimentRun.error_category, func.count())
        .where(
            ExperimentRun.experiment_id == experiment_id,
            ExperimentRun.error_category.is_not(None),
        )
        .group_by(ExperimentRun.error_category)
    ).all()
    error_groups: dict[str, int] = {
        category: count for category, count in error_rows if category is not None
    }
    return {
        "id": experiment.id,
        "name": experiment.name,
        "status": experiment.status,
        "progress": experiment.progress,
        "total_cost": experiment.total_cost,
        "currency": experiment.currency,
        "configuration": {
            "parameters": experiment.parameters,
            "evaluators": experiment.evaluator_config,
            "weights": experiment.recommendation_weights,
        },
        "metrics": metrics,
        "recommendation": recommendation,
        "errors": error_groups,
        "runs": experiment.runs,
    }


@router.put("/runs/{run_id}/review")
def review_run(
    run_id: uuid.UUID,
    payload: ManualReviewCreate,
    context: WorkspaceContext = Depends(require_roles(Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    run = db.get(ExperimentRun, run_id)
    experiment = db.get(Experiment, run.experiment_id) if run else None
    if not run or not experiment or experiment.workspace_id != context.workspace.id:
        raise HTTPException(status_code=404, detail="Run not found")
    review = db.scalar(
        select(ManualReview).where(
            ManualReview.run_id == run_id, ManualReview.reviewer_id == context.user.id
        )
    )
    if review:
        for key, value in payload.model_dump().items():
            setattr(review, key, value)
    else:
        review = ManualReview(run_id=run_id, reviewer_id=context.user.id, **payload.model_dump())
        db.add(review)
    audit(db, context.workspace.id, context.user.id, "run.reviewed", "run", run_id)
    db.commit()
    return {"id": review.id, "stars": review.stars}
