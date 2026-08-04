from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import (
    Dataset,
    DatasetVersion,
    Experiment,
    ExperimentRun,
    Prompt,
    PromptVersion,
    Report,
    User,
    WorkspaceMember,
)
from app.schemas.dataset import TestCaseInput as DatasetCaseInput
from app.services.demo_service import seed_demo
from app.services.report_service import report_service
from app.services.resource_service import resource_service


def test_prompt_and_dataset_edits_create_versions_and_can_be_archived(db) -> None:
    seed_demo(db)
    user = db.scalar(select(User))
    membership = db.scalar(select(WorkspaceMember))
    prompt = db.scalar(select(Prompt).options(selectinload(Prompt.versions)))
    dataset = db.scalar(select(Dataset).options(selectinload(Dataset.versions)))
    assert user and membership and prompt and dataset

    original_prompt_version_id = prompt.versions[-1].id
    original_dataset_version_id = dataset.versions[-1].id
    resource_service.update_prompt(
        db,
        membership.workspace_id,
        user.id,
        prompt.id,
        name="Updated support prompt",
        description="Updated description",
        tags=["support", "updated"],
        system_prompt="Return a concise answer.",
        user_template="Classify: {{input_text}}",
        response_format="json",
    )
    resource_service.update_dataset(
        db,
        membership.workspace_id,
        user.id,
        dataset.id,
        name="Updated support dataset",
        description="Updated description",
        cases=[
            DatasetCaseInput(
                name="Updated case",
                inputs={"input_text": "Where is my order?"},
                expected_output={"category": "question"},
            )
        ],
    )

    db.expire_all()
    updated_prompt = db.scalar(
        select(Prompt).options(selectinload(Prompt.versions)).where(Prompt.id == prompt.id)
    )
    updated_dataset = db.scalar(
        select(Dataset).options(selectinload(Dataset.versions)).where(Dataset.id == dataset.id)
    )
    assert updated_prompt and updated_dataset
    assert [item.version for item in updated_prompt.versions] == [1, 2]
    assert [item.version for item in updated_dataset.versions] == [1, 2]
    assert db.get(PromptVersion, original_prompt_version_id) is not None
    assert db.get(DatasetVersion, original_dataset_version_id) is not None

    resource_service.archive_prompt(db, membership.workspace_id, user.id, updated_prompt.id)
    resource_service.archive_dataset(db, membership.workspace_id, user.id, updated_dataset.id)
    db.expire_all()
    assert db.get(Prompt, updated_prompt.id).is_archived is True
    assert db.get(Dataset, updated_dataset.id).is_archived is True


def test_report_and_experiment_deletion_remove_records_and_files(db, tmp_path: Path) -> None:
    seed_demo(db)
    user = db.scalar(select(User))
    membership = db.scalar(select(WorkspaceMember))
    experiment = db.scalar(select(Experiment))
    assert user and membership and experiment

    original_directory = settings.report_directory
    settings.report_directory = tmp_path
    try:
        report = report_service.generate(db, experiment.id, user.id, "json", "PLN")
        report_path = Path(report.file_path)
        assert report_path.is_file()
        resource_service.delete_report(db, membership.workspace_id, user.id, report.id)
        assert db.get(Report, report.id) is None
        assert not report_path.exists()

        second_report = report_service.generate(db, experiment.id, user.id, "json", "PLN")
        second_path = Path(second_report.file_path)
        resource_service.delete_experiment(db, membership.workspace_id, user.id, experiment.id)
        assert db.get(Experiment, experiment.id) is None
        assert db.scalar(select(func.count()).select_from(ExperimentRun)) == 0
        assert db.scalar(select(func.count()).select_from(Report)) == 0
        assert not second_path.exists()
    finally:
        settings.report_directory = original_directory
