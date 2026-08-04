from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import (
    Dataset,
    DatasetVersion,
    Experiment,
    ExperimentRun,
    ManualReview,
    Prompt,
    PromptVersion,
    RegressionResult,
    Report,
    TestCase,
)
from app.models.entities import ExperimentStatus
from app.schemas.dataset import TestCaseInput
from app.services.audit_service import audit
from app.services.experiment_service import extract_variables
from app.services.showcase_service import ensure_writable


class ResourceService:
    """Update versioned resources and safely remove workspace owned records."""

    def update_prompt(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        prompt_id: uuid.UUID,
        *,
        name: str,
        description: str,
        tags: list[str],
        system_prompt: str,
        user_template: str,
        response_format: str,
    ) -> Prompt:
        ensure_writable()
        prompt = db.scalar(
            select(Prompt)
            .options(selectinload(Prompt.versions))
            .where(Prompt.id == prompt_id, Prompt.workspace_id == workspace_id)
        )
        if not prompt or prompt.is_archived:
            raise ValueError("Prompt not found")
        clean_name = name.strip()
        if not clean_name or not user_template.strip():
            raise ValueError("Name and user template are required")
        latest = prompt.versions[-1]
        prompt.name = clean_name
        prompt.description = description.strip()
        prompt.tags = tags
        db.add(
            PromptVersion(
                prompt_id=prompt.id,
                version=latest.version + 1,
                system_prompt=system_prompt,
                user_template=user_template,
                variables=extract_variables(user_template),
                response_format=response_format,
                json_schema=latest.json_schema,
                change_note="Updated from the user interface",
                created_by_id=actor_id,
            )
        )
        audit(db, workspace_id, actor_id, "update", "prompt", prompt.id)
        db.commit()
        return prompt

    def archive_prompt(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        prompt_id: uuid.UUID,
    ) -> None:
        ensure_writable()
        prompt = db.scalar(
            select(Prompt).where(Prompt.id == prompt_id, Prompt.workspace_id == workspace_id)
        )
        if not prompt:
            raise ValueError("Prompt not found")
        prompt.is_archived = True
        audit(db, workspace_id, actor_id, "archive", "prompt", prompt.id)
        db.commit()

    def update_dataset(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        dataset_id: uuid.UUID,
        *,
        name: str,
        description: str,
        cases: list[TestCaseInput],
    ) -> Dataset:
        ensure_writable()
        dataset = db.scalar(
            select(Dataset)
            .options(selectinload(Dataset.versions))
            .where(Dataset.id == dataset_id, Dataset.workspace_id == workspace_id)
        )
        if not dataset or dataset.is_archived:
            raise ValueError("Dataset not found")
        clean_name = name.strip()
        if not clean_name or not cases:
            raise ValueError("Name and at least one test case are required")
        dataset.name = clean_name
        dataset.description = description.strip()
        version = DatasetVersion(
            dataset_id=dataset.id,
            version=dataset.versions[-1].version + 1,
            required_variables=sorted({key for case in cases for key in case.inputs}),
            change_note="Updated from the user interface",
            created_by_id=actor_id,
        )
        db.add(version)
        db.flush()
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
        audit(db, workspace_id, actor_id, "update", "dataset", dataset.id)
        db.commit()
        return dataset

    def archive_dataset(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        dataset_id: uuid.UUID,
    ) -> None:
        ensure_writable()
        dataset = db.scalar(
            select(Dataset).where(Dataset.id == dataset_id, Dataset.workspace_id == workspace_id)
        )
        if not dataset:
            raise ValueError("Dataset not found")
        dataset.is_archived = True
        audit(db, workspace_id, actor_id, "archive", "dataset", dataset.id)
        db.commit()

    def update_experiment(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        experiment_id: uuid.UUID,
        *,
        name: str,
        description: str,
        maximum_budget: float | None,
    ) -> Experiment:
        ensure_writable()
        experiment = db.scalar(
            select(Experiment).where(
                Experiment.id == experiment_id, Experiment.workspace_id == workspace_id
            )
        )
        if not experiment:
            raise ValueError("Experiment not found")
        if experiment.status in {ExperimentStatus.QUEUED, ExperimentStatus.RUNNING}:
            raise ValueError("A queued or running experiment cannot be edited")
        if not name.strip():
            raise ValueError("Name is required")
        experiment.name = name.strip()
        experiment.description = description.strip()
        experiment.maximum_budget = maximum_budget
        audit(db, workspace_id, actor_id, "update", "experiment", experiment.id)
        db.commit()
        return experiment

    def delete_experiment(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        experiment_id: uuid.UUID,
    ) -> None:
        ensure_writable()
        experiment = db.scalar(
            select(Experiment)
            .options(selectinload(Experiment.runs), selectinload(Experiment.models))
            .where(Experiment.id == experiment_id, Experiment.workspace_id == workspace_id)
        )
        if not experiment:
            raise ValueError("Experiment not found")
        if experiment.status in {ExperimentStatus.QUEUED, ExperimentStatus.RUNNING}:
            raise ValueError("A queued or running experiment cannot be deleted")

        run_ids = list(
            db.scalars(select(ExperimentRun.id).where(ExperimentRun.experiment_id == experiment.id))
        )
        if run_ids:
            db.execute(delete(ManualReview).where(ManualReview.run_id.in_(run_ids)))

        reports = list(db.scalars(select(Report).where(Report.experiment_id == experiment.id)))
        report_paths = [item.file_path for item in reports]
        db.execute(delete(Report).where(Report.experiment_id == experiment.id))
        db.execute(
            delete(RegressionResult).where(
                or_(
                    RegressionResult.experiment_id == experiment.id,
                    RegressionResult.baseline_experiment_id == experiment.id,
                )
            )
        )
        db.execute(
            update(Experiment)
            .where(Experiment.baseline_experiment_id == experiment.id)
            .values(baseline_experiment_id=None)
        )
        audit(db, workspace_id, actor_id, "delete", "experiment", experiment.id)
        db.delete(experiment)
        db.commit()
        for path in report_paths:
            self._remove_report_file(path)

    def delete_report(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> None:
        ensure_writable()
        report = db.scalar(
            select(Report)
            .join(Experiment)
            .where(Report.id == report_id, Experiment.workspace_id == workspace_id)
        )
        if not report:
            raise ValueError("Report not found")
        path = report.file_path
        has_another_reference = bool(
            db.scalar(
                select(Report.id).where(Report.file_path == path, Report.id != report.id).limit(1)
            )
        )
        audit(db, workspace_id, actor_id, "delete", "report", report.id)
        db.delete(report)
        db.commit()
        if not has_another_reference:
            self._remove_report_file(path)

    @staticmethod
    def _remove_report_file(file_path: str) -> None:
        candidate = Path(file_path).resolve()
        report_root = settings.report_directory.resolve()
        if candidate.is_relative_to(report_root):
            candidate.unlink(missing_ok=True)


resource_service = ResourceService()
