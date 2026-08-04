from __future__ import annotations

import json

from nicegui import ui
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import Dataset, DatasetVersion, Prompt, PromptVersion, TestCase
from app.schemas.dataset import TestCaseInput
from app.services.experiment_service import extract_variables
from app.services.resource_service import resource_service
from app.ui.components import confirmation_dialog
from app.ui.i18n import t
from app.ui.layout import page_frame, require_user, workspace_for_user


def register() -> None:
    @ui.page("/prompts")
    def prompts_page() -> None:
        user = require_user()
        if not user:
            return
        workspace = workspace_for_user(user.id)
        if workspace is None:
            return
        with SessionLocal() as db:
            prompts = list(
                db.scalars(
                    select(Prompt)
                    .options(selectinload(Prompt.versions))
                    .where(Prompt.workspace_id == workspace.id, Prompt.is_archived.is_(False))
                    .order_by(Prompt.updated_at.desc())
                )
            )
        with page_frame("prompts"):
            with ui.row().classes("w-full justify-end"):
                dialog = ui.dialog()
                ui.button(t("new_prompt"), icon="add", on_click=dialog.open).props("unelevated")
            with dialog, ui.card().classes("w-[760px] max-w-full p-5"):
                ui.label(t("new_prompt")).classes("text-xl font-semibold")
                name = ui.input(t("name")).props("outlined").classes("w-full")
                description = ui.input(t("description")).props("outlined").classes("w-full")
                tags = ui.input(t("tags")).props("outlined").classes("w-full")
                system_prompt = (
                    ui.textarea(t("system_prompt")).props("outlined autogrow").classes("w-full")
                )
                template = (
                    ui.textarea(t("user_template")).props("outlined autogrow").classes("w-full")
                )
                response_format = (
                    ui.select(
                        {"text": "Text", "json": "JSON", "json_schema": "JSON Schema"},
                        value="text",
                        label=t("format"),
                    )
                    .props("outlined")
                    .classes("w-full")
                )

                def create_prompt() -> None:
                    if not name.value or not template.value:
                        ui.notify("Name and user template are required", type="warning")
                        return
                    with SessionLocal() as action_db:
                        prompt = Prompt(
                            workspace_id=workspace.id,
                            name=name.value,
                            description=description.value or "",
                            tags=[
                                item.strip()
                                for item in (tags.value or "").split(",")
                                if item.strip()
                            ],
                            created_by_id=user.id,
                        )
                        action_db.add(prompt)
                        action_db.flush()
                        action_db.add(
                            PromptVersion(
                                prompt_id=prompt.id,
                                version=1,
                                system_prompt=system_prompt.value or "",
                                user_template=template.value,
                                variables=extract_variables(template.value),
                                response_format=response_format.value,
                                created_by_id=user.id,
                            )
                        )
                        action_db.commit()
                    dialog.close()
                    ui.notify(t("saved"), type="positive")
                    ui.navigate.reload()

                with ui.row().classes("w-full justify-end"):
                    ui.button(t("cancel"), on_click=dialog.close).props("flat")
                    ui.button(t("create"), on_click=create_prompt).props("unelevated")
            if not prompts:
                with ui.card().classes("ef-card w-full p-10 items-center"):
                    ui.icon("terminal", size="48px", color="grey")
                    ui.label(t("no_data")).classes("ef-muted")
            with ui.element("div").classes("ef-card-grid"):

                def render_prompt_card(prompt_item: Prompt) -> None:
                    latest = prompt_item.versions[-1]
                    edit_dialog = ui.dialog()
                    with edit_dialog, ui.card().classes("w-[760px] max-w-full p-5"):
                        ui.label(t("edit_prompt")).classes("text-xl font-semibold")
                        edit_name = (
                            ui.input(t("name"), value=prompt_item.name)
                            .props("outlined")
                            .classes("w-full")
                        )
                        edit_description = (
                            ui.input(t("description"), value=prompt_item.description)
                            .props("outlined")
                            .classes("w-full")
                        )
                        edit_tags = (
                            ui.input(t("tags"), value=", ".join(prompt_item.tags))
                            .props("outlined")
                            .classes("w-full")
                        )
                        edit_system = (
                            ui.textarea(t("system_prompt"), value=latest.system_prompt)
                            .props("outlined autogrow")
                            .classes("w-full")
                        )
                        edit_template = (
                            ui.textarea(t("user_template"), value=latest.user_template)
                            .props("outlined autogrow")
                            .classes("w-full")
                        )
                        edit_format = (
                            ui.select(
                                {
                                    "text": "Text",
                                    "json": "JSON",
                                    "json_schema": "JSON Schema",
                                },
                                value=latest.response_format,
                                label=t("format"),
                            )
                            .props("outlined")
                            .classes("w-full")
                        )

                        def save_prompt() -> None:
                            try:
                                with SessionLocal() as action_db:
                                    resource_service.update_prompt(
                                        action_db,
                                        workspace.id,
                                        user.id,
                                        prompt_item.id,
                                        name=edit_name.value or "",
                                        description=edit_description.value or "",
                                        tags=[
                                            item.strip()
                                            for item in (edit_tags.value or "").split(",")
                                            if item.strip()
                                        ],
                                        system_prompt=edit_system.value or "",
                                        user_template=edit_template.value or "",
                                        response_format=edit_format.value,
                                    )
                                edit_dialog.close()
                                ui.notify(t("saved"), type="positive")
                                ui.navigate.reload()
                            except ValueError as exc:
                                ui.notify(str(exc), type="negative")

                        with ui.row().classes("w-full justify-end"):
                            ui.button(t("cancel"), on_click=edit_dialog.close).props("flat")
                            ui.button(t("save"), icon="save", on_click=save_prompt).props(
                                "unelevated"
                            )

                    def archive_prompt() -> None:
                        try:
                            with SessionLocal() as action_db:
                                resource_service.archive_prompt(
                                    action_db, workspace.id, user.id, prompt_item.id
                                )
                            ui.notify(t("deleted"), type="positive")
                            ui.navigate.reload()
                        except ValueError as exc:
                            ui.notify(str(exc), type="negative")

                    delete_dialog = confirmation_dialog(
                        t("delete_prompt_title"), t("delete_prompt_message"), archive_prompt
                    )
                    with ui.card().classes("ef-card p-5"):
                        with ui.row().classes("w-full items-start"):
                            ui.icon("terminal", color="primary", size="28px")
                            ui.space()
                            ui.badge(f"v{latest.version}", color="primary")
                        ui.label(prompt_item.name).classes("text-lg font-semibold mt-2")
                        ui.label(prompt_item.description or " ").classes(
                            "ef-muted text-sm min-h-10"
                        )
                        with ui.row().classes("gap-2 mt-2"):
                            for tag in prompt_item.tags:
                                ui.badge(tag, color="grey").props("outline")
                        ui.separator().classes("my-3")
                        ui.label(
                            f"{t('variables')}: {', '.join(latest.variables) or 'none'}"
                        ).classes("text-xs ef-muted")
                        with ui.row().classes("w-full justify-end mt-2"):
                            ui.button(t("edit"), icon="edit", on_click=edit_dialog.open).props(
                                "flat"
                            )
                            ui.button(
                                t("delete"), icon="delete", on_click=delete_dialog.open
                            ).props("flat color=negative")

                for prompt_item in prompts:
                    render_prompt_card(prompt_item)

    @ui.page("/datasets")
    def datasets_page() -> None:
        user = require_user()
        if not user:
            return
        workspace = workspace_for_user(user.id)
        if workspace is None:
            return
        with SessionLocal() as db:
            datasets = list(
                db.scalars(
                    select(Dataset)
                    .options(selectinload(Dataset.versions).selectinload(DatasetVersion.test_cases))
                    .where(Dataset.workspace_id == workspace.id, Dataset.is_archived.is_(False))
                    .order_by(Dataset.updated_at.desc())
                )
            )
        with page_frame("datasets"):
            with ui.row().classes("w-full justify-end"):
                dialog = ui.dialog()
                ui.button(t("new_dataset"), icon="add", on_click=dialog.open).props("unelevated")
            with dialog, ui.card().classes("w-[780px] max-w-full p-5"):
                ui.label(t("new_dataset")).classes("text-xl font-semibold")
                name = ui.input(t("name")).props("outlined").classes("w-full")
                description = ui.input(t("description")).props("outlined").classes("w-full")
                sample = json.dumps(
                    [
                        {
                            "name": "Example 1",
                            "inputs": {"input_text": "Customer message"},
                            "expected_output": {"category": "question"},
                            "expected_keywords": ["question"],
                            "difficulty": "easy",
                        }
                    ],
                    indent=2,
                )
                cases_json = (
                    ui.textarea(t("dataset_json"), value=sample)
                    .props("outlined rows=14")
                    .classes("w-full font-mono")
                )

                def create_dataset() -> None:
                    try:
                        cases = [
                            TestCaseInput.model_validate(item)
                            for item in json.loads(cases_json.value)
                        ]
                        if not cases:
                            raise ValueError("At least one test case is required")
                    except Exception as exc:
                        ui.notify(str(exc), type="negative")
                        return
                    with SessionLocal() as action_db:
                        dataset = Dataset(
                            workspace_id=workspace.id,
                            name=name.value,
                            description=description.value or "",
                            created_by_id=user.id,
                        )
                        action_db.add(dataset)
                        action_db.flush()
                        version = DatasetVersion(
                            dataset_id=dataset.id,
                            version=1,
                            required_variables=sorted(
                                {key for case in cases for key in case.inputs}
                            ),
                            created_by_id=user.id,
                        )
                        action_db.add(version)
                        action_db.flush()
                        for case in cases:
                            action_db.add(
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
                        action_db.commit()
                    dialog.close()
                    ui.notify(t("saved"), type="positive")
                    ui.navigate.reload()

                with ui.row().classes("w-full justify-end"):
                    ui.button(t("cancel"), on_click=dialog.close).props("flat")
                    ui.button(t("create"), on_click=create_dataset).props("unelevated")
            with ui.element("div").classes("ef-card-grid"):

                def render_dataset_card(dataset_item: Dataset) -> None:
                    version = dataset_item.versions[-1]
                    serialized_cases = json.dumps(
                        [
                            {
                                "name": case.name,
                                "inputs": case.inputs,
                                "expected_output": case.expected_output,
                                "expected_keywords": case.expected_keywords,
                                "reference_context": case.reference_context,
                                "metadata": case.extra_metadata,
                                "difficulty": case.difficulty,
                            }
                            for case in version.test_cases
                        ],
                        indent=2,
                        ensure_ascii=False,
                    )
                    edit_dialog = ui.dialog()
                    with edit_dialog, ui.card().classes("w-[780px] max-w-full p-5"):
                        ui.label(t("edit_dataset")).classes("text-xl font-semibold")
                        edit_name = (
                            ui.input(t("name"), value=dataset_item.name)
                            .props("outlined")
                            .classes("w-full")
                        )
                        edit_description = (
                            ui.input(t("description"), value=dataset_item.description)
                            .props("outlined")
                            .classes("w-full")
                        )
                        edit_cases = (
                            ui.textarea(t("dataset_json"), value=serialized_cases)
                            .props("outlined rows=14")
                            .classes("w-full font-mono")
                        )

                        def save_dataset() -> None:
                            try:
                                cases = [
                                    TestCaseInput.model_validate(item)
                                    for item in json.loads(edit_cases.value or "[]")
                                ]
                                with SessionLocal() as action_db:
                                    resource_service.update_dataset(
                                        action_db,
                                        workspace.id,
                                        user.id,
                                        dataset_item.id,
                                        name=edit_name.value or "",
                                        description=edit_description.value or "",
                                        cases=cases,
                                    )
                                edit_dialog.close()
                                ui.notify(t("saved"), type="positive")
                                ui.navigate.reload()
                            except Exception as exc:
                                ui.notify(str(exc), type="negative")

                        with ui.row().classes("w-full justify-end"):
                            ui.button(t("cancel"), on_click=edit_dialog.close).props("flat")
                            ui.button(t("save"), icon="save", on_click=save_dataset).props(
                                "unelevated"
                            )

                    def archive_dataset() -> None:
                        try:
                            with SessionLocal() as action_db:
                                resource_service.archive_dataset(
                                    action_db, workspace.id, user.id, dataset_item.id
                                )
                            ui.notify(t("deleted"), type="positive")
                            ui.navigate.reload()
                        except ValueError as exc:
                            ui.notify(str(exc), type="negative")

                    delete_dialog = confirmation_dialog(
                        t("delete_dataset_title"), t("delete_dataset_message"), archive_dataset
                    )
                    with ui.card().classes("ef-card p-5"):
                        with ui.row().classes("w-full items-center"):
                            ui.icon("dataset", color="primary", size="28px")
                            ui.space()
                            ui.badge(f"v{version.version}", color="primary")
                        ui.label(dataset_item.name).classes("text-lg font-semibold mt-2")
                        ui.label(dataset_item.description or " ").classes(
                            "ef-muted text-sm min-h-10"
                        )
                        ui.separator().classes("my-3")
                        with ui.row().classes("w-full"):
                            ui.label(f"{len(version.test_cases)} {t('cases').lower()}").classes(
                                "text-sm font-medium"
                            )
                            ui.space()
                            ui.label(", ".join(version.required_variables)).classes(
                                "text-xs ef-muted"
                            )
                        with ui.row().classes("w-full justify-end mt-2"):
                            ui.button(t("edit"), icon="edit", on_click=edit_dialog.open).props(
                                "flat"
                            )
                            ui.button(
                                t("delete"), icon="delete", on_click=delete_dialog.open
                            ).props("flat color=negative")

                for dataset_item in datasets:
                    render_dataset_card(dataset_item)
