from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from app.ui.i18n import t


def confirmation_dialog(title: str, message: str, on_confirm: Callable[[], None]) -> ui.dialog:
    dialog = ui.dialog()
    with dialog, ui.card().classes("w-[480px] max-w-full p-5"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("warning", color="negative", size="30px")
            ui.label(title).classes("text-xl font-semibold")
        ui.label(message).classes("ef-muted")

        def confirm() -> None:
            dialog.close()
            on_confirm()

        with ui.row().classes("w-full justify-end mt-3"):
            ui.button(t("cancel"), on_click=dialog.close).props("flat")
            ui.button(t("delete"), icon="delete", on_click=confirm).props(
                "unelevated color=negative"
            )
    return dialog
