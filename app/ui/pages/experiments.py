from __future__ import annotations

import uuid

from nicegui import ui
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import (
    Dataset,
    DatasetVersion,
    Experiment,
    ExperimentRun,
    LLMModel,
    Prompt,
    PromptVersion,
)
from app.schemas.experiment import ExperimentCreate
from app.services.experiment_service import experiment_service
from app.services.metrics_service import metrics_service
from app.services.queue_service import QueueUnavailableError, enqueue_experiment
from app.services.recommendation_service import recommendation_service
from app.ui.i18n import t
from app.ui.layout import page_frame, require_user, workspace_for_user


def register() -> None:
    @ui.page("/experiments")
    def experiments_page() -> None:
        user = require_user()
        if not user:
            return
        workspace = workspace_for_user(user.id)
        if workspace is None:
            return
        with SessionLocal() as db:
            experiments = list(
                db.scalars(
                    select(Experiment)
                    .where(Experiment.workspace_id == workspace.id)
                    .order_by(Experiment.created_at.desc())
                )
            )
            prompt_versions = list(
                db.scalars(
                    select(PromptVersion)
                    .join(Prompt)
                    .where(Prompt.workspace_id == workspace.id, Prompt.is_archived.is_(False))
                )
            )
            dataset_versions = list(
                db.scalars(
                    select(DatasetVersion)
                    .join(Dataset)
                    .where(Dataset.workspace_id == workspace.id, Dataset.is_archived.is_(False))
                )
            )
            models = list(
                db.scalars(
                    select(LLMModel).where(
                        LLMModel.workspace_id == workspace.id, LLMModel.is_active.is_(True)
                    )
                )
            )
            prompt_names = {}
            for prompt_version in prompt_versions:
                parent_prompt = db.get(Prompt, prompt_version.prompt_id)
                prompt_names[prompt_version.id] = parent_prompt.name if parent_prompt else "Prompt"
            dataset_names = {}
            for dataset_version in dataset_versions:
                parent_dataset = db.get(Dataset, dataset_version.dataset_id)
                dataset_names[dataset_version.id] = (
                    parent_dataset.name if parent_dataset else "Dataset"
                )
        with page_frame("experiments"):
            with ui.row().classes("w-full justify-end"):
                dialog = ui.dialog()
                ui.button(t("new_experiment"), icon="add", on_click=dialog.open).props("unelevated")
            with dialog, ui.card().classes("w-[820px] max-w-full p-5"):
                ui.label(t("new_experiment")).classes("text-xl font-semibold")
                stepper = ui.stepper().props("flat animated").classes("w-full")
                with stepper:
                    with ui.step("1", title=t("name"), icon="edit"):
                        name = ui.input(t("name")).props("outlined").classes("w-full")
                        description = ui.input(t("description")).props("outlined").classes("w-full")
                        with ui.stepper_navigation():
                            ui.button("Next", on_click=stepper.next)
                    with ui.step("2", title=t("prompt"), icon="terminal"):
                        prompt = (
                            ui.select(
                                {
                                    str(item.id): f"{prompt_names[item.id]} v{item.version}"
                                    for item in prompt_versions
                                },
                                label=t("prompt"),
                            )
                            .props("outlined")
                            .classes("w-full")
                        )
                        dataset = (
                            ui.select(
                                {
                                    str(item.id): f"{dataset_names[item.id]} v{item.version}"
                                    for item in dataset_versions
                                },
                                label=t("dataset"),
                            )
                            .props("outlined")
                            .classes("w-full")
                        )
                        with ui.stepper_navigation():
                            ui.button("Back", on_click=stepper.previous).props("flat")
                            ui.button("Next", on_click=stepper.next)
                    with ui.step("3", title=t("models"), icon="memory"):
                        selected_models = (
                            ui.select(
                                {str(item.id): item.display_name for item in models},
                                label=t("select_models"),
                                multiple=True,
                            )
                            .props("outlined use-chips")
                            .classes("w-full")
                        )
                        temperature = (
                            ui.number(t("temperature"), value=0.2, min=0, max=2, step=0.1)
                            .props("outlined")
                            .classes("w-full")
                        )
                        budget = (
                            ui.number(t("maximum_budget"), value=10, min=0.01, step=1)
                            .props("outlined")
                            .classes("w-full")
                        )

                        def create_experiment() -> None:
                            try:
                                payload = ExperimentCreate(
                                    name=name.value,
                                    description=description.value or "",
                                    prompt_version_id=uuid.UUID(prompt.value),
                                    dataset_version_id=uuid.UUID(dataset.value),
                                    model_ids=[uuid.UUID(item) for item in selected_models.value],
                                    parameters={
                                        "temperature": temperature.value,
                                        "concurrency": 4,
                                        "max_retries": 2,
                                        "timeout": 60,
                                    },
                                    evaluator_config={
                                        "exact_match": {},
                                        "json_validator": {},
                                        "schema_validator": {},
                                    },
                                    maximum_budget=budget.value,
                                    currency=workspace.default_currency,
                                )
                                with SessionLocal() as action_db:
                                    experiment_service.create(
                                        action_db, workspace.id, user.id, payload
                                    )
                                dialog.close()
                                ui.notify(t("saved"), type="positive")
                                ui.navigate.reload()
                            except Exception as exc:
                                ui.notify(str(exc), type="negative")

                        with ui.stepper_navigation():
                            ui.button("Back", on_click=stepper.previous).props("flat")
                            ui.button(t("create"), on_click=create_experiment).props("unelevated")
            with ui.card().classes("ef-card p-0 w-full"):
                if not experiments:
                    ui.label(t("no_data")).classes("p-8 ef-muted")
                for experiment_row in experiments:
                    with ui.row().classes(
                        "w-full items-center px-5 py-4 border-b border-slate-100 dark:border-slate-800"
                    ):
                        ui.icon("science", color="primary", size="28px")
                        with ui.column().classes("gap-0"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(experiment_row.name).classes("font-semibold")
                                ui.badge("DEMO", color="amber") if experiment_row.is_demo else None
                            ui.label(experiment_row.created_at.strftime("%Y.%m.%d %H:%M")).classes(
                                "text-xs ef-muted"
                            )
                        ui.space()
                        ui.linear_progress(experiment_row.progress / 100, color="primary").classes(
                            "w-32"
                        )
                        ui.badge(
                            experiment_row.status.value.replace("_", " "),
                            color="green" if "completed" in experiment_row.status.value else "blue",
                        )

                        def view(experiment_id: uuid.UUID = experiment_row.id) -> None:
                            ui.navigate.to(f"/experiments/{experiment_id}")

                        ui.button(t("view"), icon="arrow_forward", on_click=view).props("flat")
                        if experiment_row.status.value in {"draft", "paused"}:

                            def run(experiment_id: uuid.UUID = experiment_row.id) -> None:
                                try:
                                    with SessionLocal() as action_db:
                                        experiment_service.prepare_runs(action_db, experiment_id)
                                    enqueue_experiment(experiment_id)
                                    ui.notify(t("queued"), type="positive")
                                    ui.navigate.reload()
                                except (ValueError, QueueUnavailableError) as exc:
                                    ui.notify(str(exc), type="negative")

                            ui.button(t("run"), icon="play_arrow", on_click=run).props("unelevated")

    @ui.page("/experiments/{experiment_id}")
    def experiment_details_page(experiment_id: str) -> None:
        user = require_user()
        if not user:
            return
        workspace = workspace_for_user(user.id)
        if workspace is None:
            return
        try:
            parsed_id = uuid.UUID(experiment_id)
        except ValueError:
            ui.navigate.to("/experiments")
            return
        with SessionLocal() as db:
            experiment = db.scalar(
                select(Experiment)
                .options(selectinload(Experiment.runs).selectinload(ExperimentRun.evaluations))
                .where(Experiment.id == parsed_id)
            )
            if not experiment or experiment.workspace_id != workspace.id:
                ui.navigate.to("/experiments")
                return
            metrics = metrics_service.aggregate(experiment.runs)
            recommendation = recommendation_service.recommend(
                metrics, experiment.recommendation_weights or {}
            )
        with page_frame("experiments"):
            with ui.row().classes("items-center gap-3"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/experiments")).props(
                    "flat round"
                )
                ui.label(experiment.name).classes("text-2xl font-bold")
                ui.badge(experiment.status.value.replace("_", " "), color="green")
            with ui.grid(columns=4).classes("w-full gap-4 max-[800px]:grid-cols-2"):
                for label, value in [
                    (t("progress"), f"{experiment.progress:.0f}%"),
                    (t("total_cost"), f"{experiment.total_cost:.4f} {experiment.currency}"),
                    (t("cases"), str(len(experiment.runs))),
                    (t("errors"), str(sum(run.status == "failed" for run in experiment.runs))),
                ]:
                    with ui.card().classes("ef-card p-5"):
                        ui.label(label).classes("text-sm ef-muted")
                        ui.label(value).classes("text-2xl font-bold")
            with ui.tabs().classes("w-full") as tabs:
                overview = ui.tab("Overview")
                models_tab = ui.tab(t("models"))
                errors_tab = ui.tab(t("errors"))
                config_tab = ui.tab("Configuration")
            with ui.tab_panels(tabs, value=overview).classes("w-full bg-transparent"):
                with ui.tab_panel(overview):
                    with ui.card().classes("ef-card p-5"):
                        ui.label(t("recommendation")).classes("text-xl font-semibold")
                        ui.label(recommendation.get("reason", ""))
                        ui.label(
                            str(recommendation.get("recommended_model_id") or "No recommendation")
                        ).classes("text-lg text-primary font-medium")
                with ui.tab_panel(models_tab):
                    rows = [{"model": key, **value} for key, value in metrics.items()]
                    columns = [
                        {
                            "name": key,
                            "label": key.replace("_", " ").title(),
                            "field": key,
                            "sortable": True,
                        }
                        for key in [
                            "model",
                            "quality",
                            "pass_rate",
                            "mean_cost",
                            "p95_latency_ms",
                            "error_rate",
                        ]
                    ]
                    ui.table(columns=columns, rows=rows, pagination=20).classes(
                        "ef-card w-full"
                    ).props("flat bordered")
                with ui.tab_panel(errors_tab):
                    for run in experiment.runs:
                        if run.error_message:
                            ui.label(f"{run.error_category}: {run.error_message}").classes(
                                "text-negative"
                            )
                    if not any(run.error_message for run in experiment.runs):
                        ui.label(t("no_data")).classes("ef-muted")
                with ui.tab_panel(config_tab):
                    ui.code(
                        str(
                            {
                                "parameters": experiment.parameters,
                                "evaluators": experiment.evaluator_config,
                            }
                        )
                    ).classes("w-full")
