from __future__ import annotations

import asyncio
import json
from typing import Any

from nicegui import app, ui

from app.config import settings
from app.services.demo_simulator import (
    MODELS,
    SCENARIOS,
    DemoRun,
    demo_report,
    localized,
    simulate_demo,
)
from app.ui.theme import apply_theme

COPY: dict[str, dict[str, str]] = {
    "en": {
        "back": "Back to home",
        "title": "Run a complete model comparison",
        "intro": "Choose a scenario, review the prompt and dataset, then compare three simulated models under identical conditions.",
        "simulation": "Interactive simulation",
        "simulation_note": "No provider API is called. Results are deterministic, no account is required and nothing you enter is stored.",
        "scenario": "1. Choose a scenario",
        "prompt": "2. Review or edit the prompt",
        "dataset": "Test dataset",
        "models": "3. Select models",
        "run": "Run demonstration experiment",
        "select_models": "Select at least two models",
        "running": "Evaluating demonstration cases",
        "preparing": "Preparing the experiment",
        "completed": "Comparison completed",
        "results": "Experiment results",
        "quality": "Quality",
        "pass_rate": "Pass rate",
        "json_validity": "JSON validity",
        "latency": "Average latency",
        "cost": "Estimated cost",
        "tokens": "Tokens",
        "recommendation": "Recommended model",
        "comparison": "Model comparison",
        "responses": "Answers by model",
        "input": "Input",
        "expected": "Expected output",
        "answer": "Simulated model answer",
        "passed": "Passed",
        "failed": "Needs review",
        "report": "Open demonstration report",
        "download": "Download JSON report",
        "reset": "Reset demo",
        "report_title": "EvalForge demonstration report",
        "report_notice": "This is a simulated report. It is not a current benchmark of any commercial model.",
        "case": "Case",
        "status": "Status",
        "provider": "Provider",
        "score": "Weighted score",
        "privacy": "Privacy Policy",
        "terms": "Terms of Use",
        "source": "Source code",
        "close": "Close",
    },
    "pl": {
        "back": "Wróć na stronę startową",
        "title": "Uruchom pełne porównanie modeli",
        "intro": "Wybierz scenariusz, sprawdź prompt i zestaw danych, a następnie porównaj trzy symulowane modele w identycznych warunkach.",
        "simulation": "Interaktywna symulacja",
        "simulation_note": "Aplikacja nie wywołuje API dostawcy. Wyniki są deterministyczne, konto nie jest potrzebne, a wpisane dane nie są zapisywane.",
        "scenario": "1. Wybierz scenariusz",
        "prompt": "2. Sprawdź lub edytuj prompt",
        "dataset": "Testowy zestaw danych",
        "models": "3. Wybierz modele",
        "run": "Uruchom eksperyment demonstracyjny",
        "select_models": "Wybierz co najmniej dwa modele",
        "running": "Oceniam przypadki demonstracyjne",
        "preparing": "Przygotowuję eksperyment",
        "completed": "Porównanie zakończone",
        "results": "Wyniki eksperymentu",
        "quality": "Jakość",
        "pass_rate": "Skuteczność",
        "json_validity": "Poprawność JSON",
        "latency": "Średni czas",
        "cost": "Szacowany koszt",
        "tokens": "Tokeny",
        "recommendation": "Rekomendowany model",
        "comparison": "Porównanie modeli",
        "responses": "Odpowiedzi według modelu",
        "input": "Dane wejściowe",
        "expected": "Oczekiwany wynik",
        "answer": "Symulowana odpowiedź modelu",
        "passed": "Zaliczono",
        "failed": "Wymaga sprawdzenia",
        "report": "Otwórz raport demonstracyjny",
        "download": "Pobierz raport JSON",
        "reset": "Zresetuj demo",
        "report_title": "Raport demonstracyjny EvalForge",
        "report_notice": "To jest raport symulowany. Nie stanowi aktualnego benchmarku żadnego komercyjnego modelu.",
        "case": "Przypadek",
        "status": "Status",
        "provider": "Dostawca",
        "score": "Wynik ważony",
        "privacy": "Polityka prywatności",
        "terms": "Warunki korzystania",
        "source": "Kod źródłowy",
        "close": "Zamknij",
    },
}


def _language() -> str:
    return str(app.storage.user.get("language", settings.default_language))


def _copy() -> dict[str, str]:
    return COPY.get(_language(), COPY["en"])


def _header() -> None:
    copy = _copy()
    with ui.header().classes("ef-public-header items-center justify-between px-5 md:px-10"):
        with (
            ui.row()
            .classes("items-center gap-3 cursor-pointer")
            .on("click", lambda: ui.navigate.to("/welcome"))
        ):
            ui.label("EF").classes("ef-brand-mark")
            ui.label("EvalForge").classes("text-xl font-bold")
        with ui.row().classes("items-center gap-2"):
            language = (
                ui.select({"en": "EN", "pl": "PL"}, value=_language())
                .props("dense outlined options-dense")
                .classes("w-20")
            )

            def change_language() -> None:
                app.storage.user["language"] = language.value
                ui.navigate.reload()

            language.on_value_change(change_language)
            ui.button(
                copy["back"], icon="arrow_back", on_click=lambda: ui.navigate.to("/welcome")
            ).props("flat no-caps").classes("ef-demo-back")


def _footer() -> None:
    copy = _copy()
    with ui.element("footer").classes("ef-public-footer"):
        ui.label("EvalForge").classes("font-bold")
        with ui.row().classes("items-center gap-5 flex-wrap"):
            ui.link(copy["privacy"], "/privacy")
            ui.link(copy["terms"], "/terms")
            ui.link(copy["source"], "https://github.com/mlynarskim/EvalForge", new_tab=True)


def _dataset_rows(scenario_key: str, language: str) -> list[dict[str, str]]:
    scenario = SCENARIOS[scenario_key]
    return [
        {
            "case": localized(case.name, language),
            "input": localized(case.input_text, language),
            "expected": json.dumps(case.expected, ensure_ascii=False),
        }
        for case in scenario.cases
    ]


def _report_json(run: DemoRun) -> str:
    return json.dumps(demo_report(run), ensure_ascii=False, indent=2)


def register() -> None:
    @ui.page("/demo")
    def interactive_demo_page() -> None:
        apply_theme()
        ui.dark_mode(value=bool(app.storage.user.get("dark", False)))
        _header()
        copy = _copy()
        language = _language()
        with ui.column().classes("ef-demo-shell w-full"):
            with ui.column().classes("gap-4 max-w-4xl"):
                ui.badge(copy["simulation"], color="amber").props("outline")
                ui.label(copy["title"]).classes("ef-demo-title")
                ui.label(copy["intro"]).classes("ef-section-lead mt-0")
                with ui.card().classes("ef-demo w-full p-4 shadow-none"):
                    with ui.row().classes("items-start gap-3 no-wrap"):
                        ui.icon("science", color="amber", size="28px")
                        with ui.column().classes("gap-1"):
                            ui.label(copy["simulation"]).classes("font-bold")
                            ui.label(copy["simulation_note"]).classes("text-sm ef-muted")

            with ui.element("div").classes("ef-demo-builder-grid"):
                with ui.column().classes("gap-5 min-w-0"):
                    with ui.card().classes("ef-card p-5 w-full"):
                        ui.label(copy["scenario"]).classes("text-xl font-bold")
                        scenario_select = (
                            ui.select(
                                {
                                    key: localized(scenario.title, language)
                                    for key, scenario in SCENARIOS.items()
                                },
                                value="support",
                            )
                            .props("outlined options-dense")
                            .classes("w-full")
                        )
                        scenario_description = ui.label(
                            localized(SCENARIOS["support"].description, language)
                        ).classes("ef-muted")

                    with ui.card().classes("ef-card p-5 w-full"):
                        ui.label(copy["prompt"]).classes("text-xl font-bold")
                        prompt_input = (
                            ui.textarea(value=localized(SCENARIOS["support"].prompt, language))
                            .props("outlined autogrow")
                            .classes("w-full")
                        )

                    with ui.card().classes("ef-card p-0 w-full overflow-hidden"):
                        ui.label(copy["dataset"]).classes("text-xl font-bold px-5 pt-5")
                        dataset_table = ui.table(
                            columns=[
                                {"name": "case", "label": copy["case"], "field": "case"},
                                {"name": "input", "label": copy["input"], "field": "input"},
                                {
                                    "name": "expected",
                                    "label": copy["expected"],
                                    "field": "expected",
                                },
                            ],
                            rows=_dataset_rows("support", language),
                            pagination=5,
                        ).props("flat wrap-cells")

                with ui.column().classes("gap-5 min-w-0"):
                    with ui.card().classes("ef-card p-5 w-full"):
                        ui.label(copy["models"]).classes("text-xl font-bold")
                        model_select = (
                            ui.select(
                                {
                                    key: f"{model.name} · {model.provider}"
                                    for key, model in MODELS.items()
                                },
                                value=list(MODELS),
                                multiple=True,
                            )
                            .props("outlined use-chips options-dense")
                            .classes("w-full")
                        )
                        for model in MODELS.values():
                            with ui.row().classes("items-start gap-3 no-wrap"):
                                ui.icon("memory", color="primary")
                                with ui.column().classes("gap-0"):
                                    ui.label(model.name).classes("font-semibold")
                                    ui.label(localized(model.description, language)).classes(
                                        "text-sm ef-muted"
                                    )

                    running_card = ui.card().classes("ef-card p-5 w-full")
                    with running_card:
                        running_status = ui.label(copy["preparing"]).classes("font-semibold")
                        running_progress = ui.linear_progress(value=0, color="primary").classes(
                            "w-full"
                        )
                    running_card.set_visibility(False)

                    run_button = (
                        ui.button(icon="play_arrow")
                        .props("unelevated no-caps size=lg")
                        .classes("w-full")
                    )
                    run_button.set_text(copy["run"])

            results_container = ui.column().classes("w-full gap-6")

        def load_scenario() -> None:
            selected = str(scenario_select.value or "support")
            scenario = SCENARIOS[selected]
            scenario_description.set_text(localized(scenario.description, language))
            prompt_input.value = localized(scenario.prompt, language)
            dataset_table.rows = _dataset_rows(selected, language)
            dataset_table.update()
            results_container.clear()

        scenario_select.on_value_change(load_scenario)

        def render_results(run: DemoRun) -> None:
            results_container.clear()
            report_content = _report_json(run)
            recommended = next(
                result for result in run.results if result.model_key == run.recommendation_key
            )
            with results_container:
                ui.separator()
                with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                    ui.label(copy["results"]).classes("ef-section-title")
                    ui.badge(copy["completed"], color="positive")

                with ui.card().classes("ef-recommendation-card ef-card p-6 w-full"):
                    with ui.row().classes("items-center gap-4"):
                        ui.icon("verified", color="positive", size="42px")
                        with ui.column().classes("gap-1"):
                            ui.label(copy["recommendation"]).classes("text-sm ef-muted")
                            ui.label(recommended.model_name).classes("text-2xl font-bold")
                            ui.label(run.recommendation_reason).classes("ef-muted")

                with ui.element("div").classes("ef-demo-results-grid"):
                    for result in run.results:
                        is_recommended = result.model_key == run.recommendation_key
                        with ui.card().classes(
                            "ef-card ef-model-result p-5"
                            + (" ef-model-recommended" if is_recommended else "")
                        ):
                            with ui.row().classes("w-full items-start"):
                                with ui.column().classes("gap-0"):
                                    ui.label(result.model_name).classes("text-xl font-bold")
                                    ui.label(result.provider).classes("text-sm ef-muted")
                                ui.space()
                                if is_recommended:
                                    ui.badge(copy["recommendation"], color="positive")
                            with ui.element("div").classes("ef-model-metrics"):
                                for label, value in (
                                    (copy["quality"], f"{result.quality:.0%}"),
                                    (copy["pass_rate"], f"{result.pass_rate:.0%}"),
                                    (copy["latency"], f"{result.average_latency_ms} ms"),
                                    (copy["cost"], f"€{result.total_cost_eur:.4f}"),
                                ):
                                    with ui.element("div"):
                                        ui.label(value).classes("text-lg font-bold")
                                        ui.label(label).classes("text-xs ef-muted")

                ui.label(copy["comparison"]).classes("text-2xl font-bold mt-4")
                comparison_rows = [
                    {
                        "model": result.model_name,
                        "provider": result.provider,
                        "quality": f"{result.quality:.0%}",
                        "pass_rate": f"{result.pass_rate:.0%}",
                        "json": f"{result.json_validity:.0%}",
                        "latency": f"{result.average_latency_ms} ms",
                        "tokens": result.total_tokens,
                        "cost": f"€{result.total_cost_eur:.4f}",
                        "score": f"{result.weighted_score:.3f}",
                    }
                    for result in run.results
                ]
                ui.table(
                    columns=[
                        {"name": "model", "label": "Model", "field": "model"},
                        {"name": "provider", "label": copy["provider"], "field": "provider"},
                        {"name": "quality", "label": copy["quality"], "field": "quality"},
                        {
                            "name": "pass_rate",
                            "label": copy["pass_rate"],
                            "field": "pass_rate",
                        },
                        {"name": "json", "label": copy["json_validity"], "field": "json"},
                        {"name": "latency", "label": copy["latency"], "field": "latency"},
                        {"name": "tokens", "label": copy["tokens"], "field": "tokens"},
                        {"name": "cost", "label": copy["cost"], "field": "cost"},
                        {"name": "score", "label": copy["score"], "field": "score"},
                    ],
                    rows=comparison_rows,
                    pagination=10,
                ).classes("ef-card w-full").props("flat bordered")

                with ui.element("div").classes("ef-charts-grid"):
                    with ui.card().classes("ef-card p-5 min-w-0"):
                        ui.label(copy["quality"]).classes("text-xl font-bold")
                        ui.echart(
                            {
                                "xAxis": {
                                    "type": "category",
                                    "data": [result.model_name for result in run.results],
                                },
                                "yAxis": {"type": "value", "min": 0, "max": 1},
                                "series": [
                                    {
                                        "type": "bar",
                                        "data": [result.quality for result in run.results],
                                        "itemStyle": {"color": "#635bff"},
                                    }
                                ],
                                "tooltip": {"trigger": "axis"},
                            }
                        ).classes("w-full h-72")
                    with ui.card().classes("ef-card p-5 min-w-0"):
                        ui.label(copy["latency"]).classes("text-xl font-bold")
                        ui.echart(
                            {
                                "xAxis": {
                                    "type": "category",
                                    "data": [result.model_name for result in run.results],
                                },
                                "yAxis": {"type": "value"},
                                "series": [
                                    {
                                        "type": "bar",
                                        "data": [
                                            result.average_latency_ms for result in run.results
                                        ],
                                        "itemStyle": {"color": "#16a085"},
                                    }
                                ],
                                "tooltip": {"trigger": "axis"},
                            }
                        ).classes("w-full h-72")

                ui.label(copy["responses"]).classes("text-2xl font-bold mt-4")
                result_tabs: list[Any] = []
                with ui.tabs().classes("w-full") as result_tabs_control:
                    for result in run.results:
                        result_tabs.append(ui.tab(result.model_name))
                with ui.tab_panels(result_tabs_control, value=result_tabs[0]).classes(
                    "w-full bg-transparent p-0"
                ):
                    for tab, result in zip(result_tabs, run.results, strict=True):
                        with ui.tab_panel(tab).classes("px-0"):
                            for case_result in result.cases:
                                status_text = (
                                    copy["passed"] if case_result.passed else copy["failed"]
                                )
                                with ui.expansion(
                                    f"{case_result.case_name} · {status_text}",
                                    icon="check_circle" if case_result.passed else "warning",
                                ).classes("ef-card w-full mb-3"):
                                    ui.label(copy["input"]).classes("font-bold")
                                    ui.label(case_result.input_text).classes("ef-muted")
                                    with ui.element("div").classes("ef-answer-grid"):
                                        with ui.column().classes("min-w-0"):
                                            ui.label(copy["expected"]).classes("font-bold")
                                            ui.code(
                                                json.dumps(
                                                    case_result.expected,
                                                    ensure_ascii=False,
                                                    indent=2,
                                                )
                                            ).classes("w-full")
                                        with ui.column().classes("min-w-0"):
                                            ui.label(copy["answer"]).classes("font-bold")
                                            ui.code(case_result.answer).classes("w-full")
                                    ui.label(
                                        f"{copy['quality']}: {case_result.quality:.0%} · {copy['latency']}: {case_result.latency_ms} ms · {copy['cost']}: €{case_result.cost_eur:.5f}"
                                    ).classes("text-xs ef-muted")

                report_dialog = ui.dialog()
                with report_dialog, ui.card().classes("w-[900px] max-w-full p-6"):
                    ui.label(copy["report_title"]).classes("text-2xl font-bold")
                    ui.label(copy["report_notice"]).classes("ef-muted")
                    with ui.element("div").classes("ef-summary-grid"):
                        for label, value in (
                            (copy["recommendation"], recommended.model_name),
                            (copy["quality"], f"{recommended.quality:.0%}"),
                            (copy["latency"], f"{recommended.average_latency_ms} ms"),
                            (copy["cost"], f"€{recommended.total_cost_eur:.4f}"),
                        ):
                            with ui.card().classes("ef-card p-4"):
                                ui.label(label).classes("text-xs ef-muted")
                                ui.label(value).classes("font-bold")
                    ui.code(report_content).classes("w-full max-h-80 overflow-auto")
                    with ui.row().classes("w-full justify-end"):
                        ui.button(copy["close"], on_click=report_dialog.close).props("flat")
                        ui.button(
                            copy["download"],
                            icon="download",
                            on_click=lambda: ui.download.content(
                                report_content,
                                filename="evalforge-demo-report.json",
                                media_type="application/json",
                            ),
                        ).props("unelevated no-caps")

                with ui.row().classes("w-full gap-3 flex-wrap pb-8"):
                    ui.button(
                        copy["report"], icon="description", on_click=report_dialog.open
                    ).props("unelevated no-caps")
                    ui.button(copy["reset"], icon="restart_alt", on_click=load_scenario).props(
                        "outline no-caps"
                    )

        async def run_experiment() -> None:
            selected_models = [str(value) for value in (model_select.value or [])]
            if len(selected_models) < 2:
                ui.notify(copy["select_models"], type="warning")
                return
            run_button.disable()
            running_card.set_visibility(True)
            running_progress.value = 0
            running_status.set_text(copy["preparing"])
            results_container.clear()
            for index in range(1, 6):
                running_status.set_text(f"{copy['running']} · {index}/5")
                running_progress.value = index / 5
                await asyncio.sleep(0.22)
            run = simulate_demo(
                scenario_key=str(scenario_select.value),
                model_keys=selected_models,
                prompt=str(prompt_input.value or ""),
                language=language,
            )
            running_status.set_text(copy["completed"])
            render_results(run)
            run_button.enable()

        run_button.on_click(run_experiment)
        _footer()
