from __future__ import annotations

import uuid

from nicegui import ui
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Experiment, Report
from app.models.entities import ExperimentStatus
from app.services.report_service import report_service
from app.services.resource_service import resource_service
from app.ui.components import confirmation_dialog
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
            if not settings.showcase_mode:
                with ui.card().classes("ef-card p-5 w-full"):
                    ui.label(t("generate_report")).classes("text-lg font-semibold")
                    experiment_select = (
                        ui.select(
                            {str(item.id): item.name for item in experiments},
                            label=t("experiments"),
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

                def render_report_row(report_item: Report) -> None:
                    def delete_report() -> None:
                        try:
                            with SessionLocal() as action_db:
                                resource_service.delete_report(
                                    action_db, workspace.id, user.id, report_item.id
                                )
                            ui.notify(t("deleted"), type="positive")
                            ui.navigate.reload()
                        except ValueError as exc:
                            ui.notify(str(exc), type="negative")

                    delete_dialog = confirmation_dialog(
                        t("delete_report_title"), t("delete_report_message"), delete_report
                    )
                    with ui.row().classes(
                        "w-full items-center p-4 border-b border-slate-100 dark:border-slate-800"
                    ):
                        ui.icon(
                            "picture_as_pdf" if report_item.format == "pdf" else "description",
                            color="primary",
                        )
                        ui.label(report_item.format.upper()).classes("font-semibold")
                        ui.label(report_item.created_at.strftime("%Y.%m.%d %H:%M")).classes(
                            "ef-muted text-sm"
                        )
                        ui.space()
                        ui.label(report_item.checksum[:12]).classes("font-mono text-xs ef-muted")
                        ui.button(
                            "Download",
                            icon="download",
                            on_click=lambda: ui.download(report_item.file_path),
                        ).props("flat")
                        if not settings.showcase_mode:
                            ui.button(icon="delete", on_click=delete_dialog.open).props(
                                f"flat round color=negative aria-label={t('delete')}"
                            )

                for report_item in reports:
                    render_report_row(report_item)
