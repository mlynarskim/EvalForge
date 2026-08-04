from __future__ import annotations

from nicegui import ui
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Experiment, Report
from app.models.entities import ExperimentStatus
from app.services.report_service import report_service
from app.ui.i18n import t
from app.ui.layout import page_frame, require_user, workspace_for_user


def register() -> None:
    @ui.page("/reports")
    def reports_page() -> None:
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
                    .where(
                        Experiment.workspace_id == workspace.id,
                        Experiment.status.in_(
                            [
                                ExperimentStatus.COMPLETED,
                                ExperimentStatus.COMPLETED_WITH_ERRORS,
                            ]
                        ),
                    )
                    .order_by(Experiment.completed_at.desc())
                )
            )
            reports = list(
                db.scalars(
                    select(Report)
                    .join(Experiment)
                    .where(Experiment.workspace_id == workspace.id)
                    .order_by(Report.created_at.desc())
                )
            )
        with page_frame("reports"):
            ui.label(t("report_help")).classes("ef-muted")
            with ui.card().classes("ef-card p-5 w-full"):
                ui.label(t("generate_report")).classes("text-lg font-semibold")
                experiment_select = (
                    ui.select(
                        {str(item.id): item.name for item in experiments}, label=t("experiments")
                    )
                    .props("outlined")
                    .classes("w-full")
                )
                format_select = (
                    ui.select(
                        {"pdf": "PDF", "html": "HTML", "csv": "CSV", "json": "JSON"},
                        value="pdf",
                        label=t("format"),
                    )
                    .props("outlined")
                    .classes("w-full")
                )

                def generate() -> None:
                    if not experiment_select.value:
                        ui.notify(t("no_data"), type="warning")
                        return
                    import uuid

                    try:
                        with SessionLocal() as action_db:
                            report_service.generate(
                                action_db,
                                uuid.UUID(experiment_select.value),
                                user.id,
                                format_select.value,
                                workspace.default_currency,
                            )
                        ui.notify(t("saved"), type="positive")
                        ui.navigate.reload()
                    except Exception as exc:
                        ui.notify(str(exc), type="negative")

                ui.button(t("generate_report"), icon="description", on_click=generate).props(
                    "unelevated"
                )
            with ui.card().classes("ef-card p-0 w-full"):
                if not reports:
                    ui.label(t("no_data")).classes("p-8 ef-muted")
                for report in reports:
                    with ui.row().classes(
                        "w-full items-center p-4 border-b border-slate-100 dark:border-slate-800"
                    ):
                        ui.icon(
                            "picture_as_pdf" if report.format == "pdf" else "description",
                            color="primary",
                        )
                        ui.label(report.format.upper()).classes("font-semibold")
                        ui.label(report.created_at.strftime("%Y.%m.%d %H:%M")).classes(
                            "ef-muted text-sm"
                        )
                        ui.space()
                        ui.label(report.checksum[:12]).classes("font-mono text-xs ef-muted")
                        ui.button(
                            "Download",
                            icon="download",
                            on_click=lambda path=report.file_path: ui.download(path),
                        ).props("flat")
