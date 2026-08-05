from __future__ import annotations

import asyncio
import json
import uuid

from nicegui import ui
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import SessionLocal
from app.models import (
    Dataset,
    DatasetVersion,
    Experiment,
    ExperimentModel,
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
from app.services.report_service import report_service
from app.services.resource_service import resource_service
from app.ui.components import confirmation_dialog
from app.ui.i18n import t
from app.ui.layout import page_frame, require_user, workspace_for_user


async def _replay_simulation(experiment_id: uuid.UUID) -> None:
    dialog = ui.dialog().props("persistent")
    with dialog, ui.card().classes("w-[520px] max-w-full p-6"):
        ui.icon("science", color="primary", size="42px")
        status = ui.label(t("simulation_running")).classes("text-xl font-semibold")
        ui.label(t("simulated_notice")).classes("ef-muted text-sm")
        progress = ui.linear_progress(value=0, color="primary").classes("w-full mt-3")
    dialog.open()
    for value in (0.08, 0.22, 0.39, 0.58, 0.76, 0.91, 1.0):
        progress.value = value
        await asyncio.sleep(0.18)
    status.set_text(t("simulation_complete"))
    await asyncio.sleep(0.35)
    dialog.close()
    ui.navigate.to(f"/experiments/{experiment_id}")


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
                if not settings.showcase_mode:
                    ui.button(t("new_experiment"), icon="add", on_click=dialog.open).props(
                        "unelevated"
                    )
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

                def render_experiment_row(experiment_item: Experiment) -> None:
                    edit_dialog = ui.dialog()
                    with edit_dialog, ui.card().classes("w-[620px] max-w-full p-5"):
                        ui.label(t("edit_experiment")).classes("text-xl font-semibold")
                        edit_name = (
                            ui.input(t("name"), value=experiment_item.name)
                            .props("outlined")
                            .classes("w-full")
                        )
                        edit_description = (
                            ui.textarea(t("description"), value=experiment_item.description)
                            .props("outlined autogrow")
                            .classes("w-full")
                        )
                        edit_budget = (
                            ui.number(
                                t("maximum_budget"),
                                value=experiment_item.maximum_budget,
                                min=0.01,
                                step=1,
                            )
                            .props("outlined")
                            .classes("w-full")
                        )

                        def save_experiment() -> None:
                            try:
                                with SessionLocal() as action_db:
                                    resource_service.update_experiment(
                                        action_db,
                                        workspace.id,
                                        user.id,
                                        experiment_item.id,
                                        name=edit_name.value or "",
                                        description=edit_description.value or "",
                                        maximum_budget=edit_budget.value,
                                    )
                                edit_dialog.close()
                                ui.notify(t("saved"), type="positive")
                                ui.navigate.reload()
                            except ValueError as exc:
                                ui.notify(str(exc), type="negative")

                        with ui.row().classes("w-full justify-end"):
                            ui.button(t("cancel"), on_click=edit_dialog.close).props("flat")
                            ui.button(t("save"), icon="save", on_click=save_experiment).props(
                                "unelevated"
                            )

                    def delete_experiment() -> None:
                        try:
                            with SessionLocal() as action_db:
                                resource_service.delete_experiment(
                                    action_db, workspace.id, user.id, experiment_item.id
                                )
                            ui.notify(t("deleted"), type="positive")
                            ui.navigate.reload()
                        except ValueError as exc:
                            ui.notify(str(exc), type="negative")

                    delete_dialog = confirmation_dialog(
                        t("delete_experiment_title"),
                        t("delete_experiment_message"),
                        delete_experiment,
                    )
                    with ui.row().classes(
                        "w-full items-center px-5 py-4 border-b border-slate-100 dark:border-slate-800"
                    ):
                        ui.icon("science", color="primary", size="28px")
                        with ui.column().classes("gap-0"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(experiment_item.name).classes("font-semibold")
                                ui.badge("DEMO", color="amber") if experiment_item.is_demo else None
                            ui.label(experiment_item.created_at.strftime("%Y.%m.%d %H:%M")).classes(
                                "text-xs ef-muted"
                            )
                        ui.space()
                        ui.linear_progress(experiment_item.progress / 100, color="primary").classes(
                            "w-32"
                        )
                        ui.badge(
                            experiment_item.status.value.replace("_", " "),
                            color="green"
                            if "completed" in experiment_item.status.value
                            else "blue",
                        )

                        def view() -> None:
                            ui.navigate.to(f"/experiments/{experiment_item.id}")

                        ui.button(t("view"), icon="arrow_forward", on_click=view).props("flat")
                        if settings.showcase_mode and experiment_item.is_demo:
                            ui.button(
                                t("replay_simulation"),
                                icon="play_arrow",
                                on_click=lambda item_id=experiment_item.id: _replay_simulation(
                                    item_id
                                ),
                            ).props("unelevated no-caps")
                        if not settings.showcase_mode:
                            ui.button(t("edit"), icon="edit", on_click=edit_dialog.open).props(
                                "flat round"
                            )
                            ui.button(icon="delete", on_click=delete_dialog.open).props(
                                f"flat round color=negative aria-label={t('delete')}"
                            )
                        if not settings.showcase_mode and experiment_item.status.value in {
                            "draft",
                            "paused",
                        }:

                            def run() -> None:
                                try:
                                    with SessionLocal() as action_db:
                                        experiment_service.prepare_runs(
                                            action_db, experiment_item.id
                                        )
                                    enqueue_experiment(experiment_item.id)
                                    ui.notify(t("queued"), type="positive")
                                    ui.navigate.reload()
                                except (ValueError, QueueUnavailableError) as exc:
                                    ui.notify(str(exc), type="negative")

                            ui.button(t("run"), icon="play_arrow", on_click=run).props("unelevated")

                for experiment_item in experiments:
                    render_experiment_row(experiment_item)

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
                .options(
                    selectinload(Experiment.runs).selectinload(ExperimentRun.evaluations),
                    selectinload(Experiment.models)
                    .selectinload(ExperimentModel.model)
                    .selectinload(LLMModel.provider),
                )
                .where(Experiment.id == parsed_id)
            )
            if not experiment or experiment.workspace_id != workspace.id:
                ui.navigate.to("/experiments")
                return
            metrics = metrics_service.aggregate(experiment.runs)
            recommendation = recommendation_service.recommend(
                metrics, experiment.recommendation_weights or {}
            )
            model_names = {
                str(item.model_id): item.model.display_name for item in experiment.models
            }
            model_providers = {
                str(item.model_id): item.model.provider.display_name for item in experiment.models
            }
            comparison_rows = [
                {
                    "model": model_names.get(model_id, model_id),
                    "provider": model_providers.get(model_id, ""),
                    "quality": round(values["quality"], 3),
                    "pass_rate": round(values["pass_rate"], 3),
                    "mean_cost": round(values["mean_cost"], 6),
                    "p95_latency_ms": round(values["p95_latency_ms"]),
                    "error_rate": round(values["error_rate"], 3),
                }
                for model_id, values in metrics.items()
            ]
            comparison_rows.sort(key=lambda row: row["quality"], reverse=True)
            recommendation_id = str(recommendation.get("recommended_model_id") or "")
            recommendation_name = model_names.get(recommendation_id, t("no_data"))
            runs_by_model: dict[str, list[ExperimentRun]] = {}
            for run in experiment.runs:
                runs_by_model.setdefault(str(run.model_id), []).append(run)
        with page_frame("experiments"):
            with ui.row().classes("items-center gap-3 w-full flex-wrap"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/experiments")).props(
                    "flat round"
                )
                ui.label(experiment.name).classes("text-2xl font-bold")
                ui.badge(experiment.status.value.replace("_", " "), color="green")
                ui.space()
                if settings.showcase_mode and experiment.is_demo:
                    ui.button(
                        t("replay_simulation"),
                        icon="play_arrow",
                        on_click=lambda: _replay_simulation(experiment.id),
                    ).props("unelevated no-caps")

                    def download_demo_report() -> None:
                        with SessionLocal() as report_db:
                            payload = report_service.payload(report_db, experiment.id)
                        content = json.dumps(payload, indent=2, ensure_ascii=False).encode()
                        ui.download.content(
                            content,
                            "evalforge-demo-report.json",
                            "application/json",
                        )

                    ui.button(
                        t("download_demo_report"),
                        icon="download",
                        on_click=download_demo_report,
                    ).props("outline no-caps")
            if experiment.is_demo:
                with ui.card().classes("ef-demo w-full p-4 shadow-none"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("info", color="amber")
                        ui.label(t("simulated_notice")).classes("font-medium")
            with ui.element("div").classes("ef-summary-grid"):
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
                overview = ui.tab(t("overview"))
                models_tab = ui.tab(t("models"))
                results_tab = ui.tab(t("results"))
                errors_tab = ui.tab(t("errors"))
                config_tab = ui.tab(t("configuration"))
            with ui.tab_panels(tabs, value=overview).classes("w-full bg-transparent"):
                with ui.tab_panel(overview):
                    with ui.card().classes("ef-card ef-recommendation-card p-5"):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("verified", color="positive", size="36px")
                            with ui.column().classes("gap-0"):
                                ui.label(t("recommendation")).classes("text-sm ef-muted")
                                ui.label(recommendation_name).classes(
                                    "text-2xl text-primary font-bold"
                                )
                        ui.label(t("recommendation_reason")).classes("ef-muted")
                    with ui.element("div").classes("ef-charts-grid mt-4"):
                        with ui.card().classes("ef-card p-5"):
                            ui.label(t("quality")).classes("text-lg font-semibold")
                            ui.echart(
                                {
                                    "tooltip": {"trigger": "axis"},
                                    "xAxis": {"type": "value", "max": 1},
                                    "yAxis": {
                                        "type": "category",
                                        "data": [row["model"] for row in comparison_rows],
                                    },
                                    "series": [
                                        {
                                            "type": "bar",
                                            "data": [row["quality"] for row in comparison_rows],
                                            "itemStyle": {"color": "#635BFF", "borderRadius": 6},
                                        }
                                    ],
                                }
                            ).classes("h-72")
                        with ui.card().classes("ef-card p-5"):
                            ui.label(t("latency")).classes("text-lg font-semibold")
                            ui.echart(
                                {
                                    "tooltip": {"trigger": "axis"},
                                    "xAxis": {
                                        "type": "category",
                                        "data": [row["model"] for row in comparison_rows],
                                    },
                                    "yAxis": {"type": "value", "name": "ms"},
                                    "series": [
                                        {
                                            "type": "bar",
                                            "data": [
                                                row["p95_latency_ms"] for row in comparison_rows
                                            ],
                                            "itemStyle": {"color": "#16A085", "borderRadius": 6},
                                        }
                                    ],
                                }
                            ).classes("h-72")
                with ui.tab_panel(models_tab):
                    columns = [
                        {
                            "name": key,
                            "label": key.replace("_", " ").title(),
                            "field": key,
                            "sortable": True,
                        }
                        for key in [
                            "model",
                            "provider",
                            "quality",
                            "pass_rate",
                            "mean_cost",
                            "p95_latency_ms",
                            "error_rate",
                        ]
                    ]
                    ui.table(columns=columns, rows=comparison_rows, pagination=20).classes(
                        "ef-card w-full"
                    ).props("flat bordered")
                with ui.tab_panel(results_tab):
                    for model_id, model_runs in runs_by_model.items():
                        model_name = model_names.get(model_id, model_id)
                        with ui.expansion(
                            f"{model_name}  •  {len(model_runs)} {t('cases').lower()}",
                            icon="memory",
                        ).classes("ef-card w-full mb-3"):
                            for run in sorted(
                                model_runs,
                                key=lambda item: str(item.dataset_snapshot.get("name", "")),
                            ):
                                evaluation = run.evaluations[0] if run.evaluations else None
                                passed = bool(evaluation and evaluation.passed)
                                case_name = str(run.dataset_snapshot.get("name", t("case")))
                                inputs = run.dataset_snapshot.get("inputs", {})
                                input_text = (
                                    str(inputs.get("input_text", ""))
                                    if isinstance(inputs, dict)
                                    else str(inputs)
                                )
                                with ui.expansion(
                                    f"{case_name}  •  {evaluation.score:.0%}"
                                    if evaluation and evaluation.score is not None
                                    else case_name,
                                    icon="check_circle" if passed else "error",
                                ).classes("w-full"):
                                    with ui.element("div").classes("ef-result-grid p-2"):
                                        with ui.column().classes("gap-2"):
                                            ui.label(t("case")).classes("text-xs ef-muted")
                                            ui.label(input_text).classes("font-medium")
                                            ui.label(t("answer")).classes("text-xs ef-muted mt-2")
                                            ui.code(run.raw_response or "").classes("w-full")
                                        with ui.column().classes("gap-2"):
                                            ui.badge(
                                                t("passed") if passed else t("errors"),
                                                color="green" if passed else "red",
                                            )
                                            ui.label(
                                                f"{t('latency')}: {run.latency_ms:.0f} ms"
                                                if run.latency_ms is not None
                                                else t("no_data")
                                            )
                                            ui.label(
                                                f"{t('total_cost')}: {run.total_cost:.6f} {experiment.currency}"
                                            )
                                            if evaluation:
                                                expected = evaluation.details.get("expected")
                                                ui.label(t("expected")).classes(
                                                    "text-xs ef-muted mt-2"
                                                )
                                                ui.code(
                                                    json.dumps(
                                                        expected,
                                                        indent=2,
                                                        ensure_ascii=False,
                                                    )
                                                ).classes("w-full")
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
