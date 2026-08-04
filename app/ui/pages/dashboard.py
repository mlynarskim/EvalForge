from __future__ import annotations

from nicegui import ui
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import EvaluationResult, Experiment, ExperimentRun, LLMModel
from app.ui.i18n import t
from app.ui.layout import page_frame, require_user, workspace_for_user


def register() -> None:
    @ui.page("/")
    def root() -> None:
        ui.navigate.to("/dashboard")

    @ui.page("/dashboard")
    def dashboard_page() -> None:
        user = require_user()
        if not user:
            return
        workspace = workspace_for_user(user.id)
        if not workspace:
            return
        with SessionLocal() as db:
            experiment_count = (
                db.scalar(
                    select(func.count())
                    .select_from(Experiment)
                    .where(Experiment.workspace_id == workspace.id)
                )
                or 0
            )
            run_count = (
                db.scalar(
                    select(func.count())
                    .select_from(ExperimentRun)
                    .join(Experiment)
                    .where(
                        Experiment.workspace_id == workspace.id, ExperimentRun.status == "completed"
                    )
                )
                or 0
            )
            cost = float(
                db.scalar(
                    select(func.sum(Experiment.total_cost)).where(
                        Experiment.workspace_id == workspace.id
                    )
                )
                or 0
            )
            quality = float(
                db.scalar(
                    select(func.avg(EvaluationResult.score))
                    .join(ExperimentRun)
                    .join(Experiment)
                    .where(
                        Experiment.workspace_id == workspace.id, EvaluationResult.score.is_not(None)
                    )
                )
                or 0
            )
            active_models = (
                db.scalar(
                    select(func.count())
                    .select_from(LLMModel)
                    .where(LLMModel.workspace_id == workspace.id, LLMModel.is_active.is_(True))
                )
                or 0
            )
            recent = list(
                db.scalars(
                    select(Experiment)
                    .where(Experiment.workspace_id == workspace.id)
                    .order_by(Experiment.created_at.desc())
                    .limit(8)
                )
            )
        with page_frame("dashboard"):
            if user.is_demo:
                with ui.row().classes("ef-demo w-full items-center p-3"):
                    ui.icon("science", color="amber")
                    ui.label(t("demo_data")).classes("font-medium")
            with ui.card().classes("ef-card p-5 w-full"):
                with ui.row().classes("w-full items-start gap-3"):
                    ui.icon("route", color="primary", size="30px")
                    with ui.column().classes("gap-1"):
                        ui.label(t("get_started")).classes("text-xl font-semibold")
                        ui.label(t("onboarding_intro")).classes("ef-muted")
                onboarding_steps = [
                    ("1", t("step_connect_title"), t("step_connect_description")),
                    ("2", t("step_prepare_title"), t("step_prepare_description")),
                    ("3", t("step_run_title"), t("step_run_description")),
                    ("4", t("step_analyze_title"), t("step_analyze_description")),
                ]
                with ui.element("div").classes("ef-onboarding-grid mt-3"):
                    for number, title, description in onboarding_steps:
                        with ui.column().classes("ef-step gap-2"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(number).classes("ef-step-number")
                                ui.label(title).classes("font-semibold")
                            ui.label(description).classes("ef-muted text-sm")
                with ui.row().classes("w-full gap-2 mt-2"):
                    ui.button(
                        t("open_providers"),
                        icon="key",
                        on_click=lambda: ui.navigate.to("/providers"),
                    ).props("unelevated")
                    ui.button(
                        t("open_demo_experiment"),
                        icon="science",
                        on_click=lambda: ui.navigate.to("/experiments"),
                    ).props("outline")
            stats = [
                (t("total_experiments"), str(experiment_count), "science", "indigo"),
                (t("completed_runs"), str(run_count), "check_circle", "green"),
                (t("total_cost"), f"{cost:.4f} {workspace.default_currency}", "payments", "violet"),
                (t("average_quality"), f"{quality:.1%}", "verified", "teal"),
                (t("active_models"), str(active_models), "memory", "blue"),
                (t("regressions"), "0", "trending_down", "orange"),
            ]
            with ui.element("div").classes("ef-stats-grid"):
                for label, value, icon, color in stats:
                    with ui.card().classes("ef-card ef-stat p-5"):
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label(label).classes("ef-muted text-sm")
                            ui.icon(icon, color=color).classes("text-2xl")
                        ui.label(value).classes("ef-stat-value text-2xl font-bold mt-3")
            with ui.element("div").classes("ef-charts-grid"):
                with ui.card().classes("ef-card p-5"):
                    ui.label(t("cost_over_time")).classes("text-lg font-semibold")
                    ui.echart(
                        {
                            "tooltip": {"trigger": "axis"},
                            "xAxis": {
                                "type": "category",
                                "data": [item.name for item in reversed(recent)],
                            },
                            "yAxis": {"type": "value"},
                            "series": [
                                {
                                    "type": "line",
                                    "smooth": True,
                                    "areaStyle": {},
                                    "data": [item.total_cost for item in reversed(recent)],
                                }
                            ],
                        }
                    ).classes("h-72")
                with ui.card().classes("ef-card p-5"):
                    ui.label(t("model_quality")).classes("text-lg font-semibold")
                    ui.echart(
                        {
                            "tooltip": {},
                            "xAxis": {"type": "value", "max": 1},
                            "yAxis": {
                                "type": "category",
                                "data": ["Demo Support Classifier"] if user.is_demo else [],
                            },
                            "series": [
                                {
                                    "type": "bar",
                                    "data": [quality] if user.is_demo else [],
                                    "itemStyle": {"color": "#635BFF", "borderRadius": 6},
                                }
                            ],
                        }
                    ).classes("h-72")
            with ui.card().classes("ef-card p-5 w-full"):
                ui.label(t("recent_activity")).classes("text-lg font-semibold mb-3")
                if not recent:
                    ui.label(t("no_data")).classes("ef-muted")
                for item in recent:
                    with ui.row().classes(
                        "w-full items-center py-2 border-b border-slate-100 dark:border-slate-800"
                    ):
                        ui.icon("science", color="primary")
                        with ui.column().classes("gap-0"):
                            ui.label(item.name).classes("font-medium")
                            ui.label(item.created_at.strftime("%Y.%m.%d %H:%M")).classes(
                                "text-xs ef-muted"
                            )
                        ui.space()
                        ui.badge(
                            item.status.value.replace("_", " "),
                            color="green" if "completed" in item.status.value else "blue",
                        )
                        ui.label(f"{item.total_cost:.4f} {item.currency}").classes("text-sm")
