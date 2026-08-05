from __future__ import annotations

from collections.abc import Callable
from typing import cast

from nicegui import app, ui

from app.config import settings
from app.ui.theme import apply_theme

COPY: dict[str, dict[str, object]] = {
    "en": {
        "sign_in": "Sign in",
        "header_demo": "Try demo",
        "demo": "Explore the live demo",
        "eyebrow": "Reproducible LLM evaluation",
        "hero_title": "Choose the right language model with evidence, not guesswork.",
        "hero_body": "Run the same prompts and test cases across providers. Compare quality, cost, latency and regressions in one clear workspace.",
        "demo_note": "No account or API key required. Results are simulated and nothing you enter is stored.",
        "value_title": "A decision workspace for teams shipping with AI",
        "value_body": "EvalForge turns scattered model tests into a repeatable process that can be reviewed, compared and shared.",
        "features": [
            (
                "One fair test",
                "Send versioned prompts and the same dataset to every selected model.",
            ),
            (
                "Useful comparisons",
                "Inspect answer quality, JSON validity, latency, token usage and estimated cost.",
            ),
            (
                "Reproducible decisions",
                "Keep experiment history, detect regressions and export client ready reports.",
            ),
        ],
        "how_title": "From question to model decision",
        "steps": [
            ("Prepare", "Select a prompt and a representative dataset."),
            ("Compare", "Evaluate several models under the same conditions."),
            ("Decide", "Review results and document the recommendation."),
        ],
        "built_with": "Open source and built primarily with Python, FastAPI and NiceGUI.",
        "privacy": "Privacy Policy",
        "terms": "Terms of Use",
        "github": "View source code",
        "back": "Back to EvalForge",
    },
    "pl": {
        "sign_in": "Zaloguj się",
        "header_demo": "Demo",
        "demo": "Otwórz demo na żywo",
        "eyebrow": "Powtarzalna ocena modeli językowych",
        "hero_title": "Wybierz właściwy model na podstawie dowodów, a nie przypuszczeń.",
        "hero_body": "Uruchamiaj te same prompty i przypadki testowe u wielu dostawców. Porównuj jakość, koszt, czas odpowiedzi i regresje w jednym miejscu.",
        "demo_note": "Bez konta i klucza API. Wyniki są symulowane, a wpisane dane nie są zapisywane.",
        "value_title": "Miejsce podejmowania decyzji dla zespołów tworzących rozwiązania AI",
        "value_body": "EvalForge zmienia rozproszone testy modeli w powtarzalny proces, który można sprawdzić, porównać i udostępnić.",
        "features": [
            (
                "Jeden uczciwy test",
                "Wysyłaj wersjonowane prompty i ten sam zestaw danych do każdego modelu.",
            ),
            (
                "Przydatne porównania",
                "Sprawdzaj jakość, poprawność JSON, czas, zużycie tokenów i szacowany koszt.",
            ),
            (
                "Powtarzalne decyzje",
                "Zachowuj historię, wykrywaj regresje i eksportuj raporty dla klienta.",
            ),
        ],
        "how_title": "Od pytania do decyzji o wyborze modelu",
        "steps": [
            ("Przygotuj", "Wybierz prompt i reprezentatywny zestaw danych."),
            ("Porównaj", "Oceń kilka modeli w tych samych warunkach."),
            ("Zdecyduj", "Sprawdź wyniki i udokumentuj rekomendację."),
        ],
        "built_with": "Projekt open source napisany głównie w Pythonie z użyciem FastAPI i NiceGUI.",
        "privacy": "Polityka prywatności",
        "terms": "Warunki korzystania",
        "github": "Zobacz kod źródłowy",
        "back": "Wróć do EvalForge",
    },
}

LEGAL: dict[str, dict[str, tuple[str, list[tuple[str, str]]]]] = {
    "en": {
        "privacy": (
            "Privacy Policy",
            [
                (
                    "Scope",
                    "This policy describes the public EvalForge demonstration operated through this website. The demonstration does not offer public account registration and should not be used to submit personal, confidential or production data.",
                ),
                (
                    "Data we process",
                    "The service uses essential session data to keep the interface working and remember language or appearance preferences. Hosting providers may process IP addresses, request metadata and technical logs needed for security, reliability and abuse prevention.",
                ),
                (
                    "Why we process it",
                    "Technical data is processed only to provide the demonstration, maintain security, diagnose failures and protect the service from misuse. EvalForge does not currently use advertising trackers or optional analytics cookies.",
                ),
                (
                    "Service providers",
                    "The demonstration is hosted by Render and stores seeded demonstration data in Neon Postgres. Source code and project information are hosted by GitHub. Each provider processes technical data under its own privacy terms.",
                ),
                (
                    "Retention",
                    "Session preferences remain until they are cleared in the browser. Infrastructure logs are retained according to the hosting providers' operational policies. The public demo does not intentionally store visitor supplied content.",
                ),
                (
                    "Your choices and rights",
                    "You may clear browser storage at any time. Where applicable, you may request access, correction, restriction or deletion of personal data and may complain to the competent data protection authority.",
                ),
                (
                    "Contact",
                    "For privacy questions, contact the project operator through the EvalForge GitHub repository. Do not include sensitive personal data in a public issue.",
                ),
                (
                    "Changes",
                    "This policy may be updated when the service, hosting or data practices change. Last updated: August 5, 2026.",
                ),
            ],
        ),
        "terms": (
            "Terms of Use",
            [
                (
                    "Public demonstration",
                    "EvalForge is currently provided as a free interactive product demonstration. It uses deterministic simulated results and does not call provider APIs. Public registration, provider credentials and persistent visitor data are disabled.",
                ),
                (
                    "Acceptable use",
                    "You may explore the demonstration for evaluation, learning and portfolio review. You must not disrupt the service, bypass access controls, probe for secrets, overload the infrastructure or use the service unlawfully.",
                ),
                (
                    "No production reliance",
                    "Demonstration results and sample data are illustrative. Do not rely on them as the sole basis for production, procurement, legal, financial or safety critical decisions.",
                ),
                (
                    "Availability and warranties",
                    "The demonstration is provided as available and may be changed, suspended or removed at any time. No guarantee is made about uninterrupted availability, accuracy or fitness for a particular purpose.",
                ),
                (
                    "Intellectual property",
                    "EvalForge source code is available under the MIT License. Third party names, services and trademarks remain the property of their respective owners.",
                ),
                (
                    "External services",
                    "Links to GitHub, Render, Neon or other providers lead to independent services governed by their own terms and policies.",
                ),
                (
                    "Changes and contact",
                    "These terms may change as the project develops. Questions can be sent through the EvalForge GitHub repository. Last updated: August 5, 2026.",
                ),
            ],
        ),
    },
    "pl": {
        "privacy": (
            "Polityka prywatności",
            [
                (
                    "Zakres",
                    "Ta polityka opisuje publiczną prezentację EvalForge udostępnioną w tej witrynie. Prezentacja nie umożliwia publicznej rejestracji i nie należy w niej umieszczać danych osobowych, poufnych ani produkcyjnych.",
                ),
                (
                    "Przetwarzane dane",
                    "Serwis korzysta z niezbędnych danych sesji, aby interfejs działał oraz pamiętał język i wygląd. Dostawcy hostingu mogą przetwarzać adres IP, metadane żądań i logi techniczne potrzebne do zapewnienia bezpieczeństwa, niezawodności i ochrony przed nadużyciami.",
                ),
                (
                    "Cel przetwarzania",
                    "Dane techniczne służą wyłącznie do udostępniania prezentacji, utrzymania bezpieczeństwa, diagnozowania awarii i ochrony serwisu. EvalForge nie korzysta obecnie z reklamowych mechanizmów śledzących ani opcjonalnych analitycznych plików cookie.",
                ),
                (
                    "Dostawcy usług",
                    "Prezentacja działa w usłudze Render, a demonstracyjne dane są przechowywane w Neon Postgres. Kod źródłowy i informacje o projekcie są dostępne w GitHub. Każdy dostawca przetwarza dane techniczne na zasadach swojej polityki prywatności.",
                ),
                (
                    "Czas przechowywania",
                    "Preferencje sesji pozostają do chwili wyczyszczenia danych przeglądarki. Logi infrastruktury są przechowywane zgodnie z zasadami operacyjnymi dostawców hostingu. Publiczne demo celowo nie zapisuje treści przekazywanych przez odwiedzających.",
                ),
                (
                    "Wybory i prawa",
                    "Możesz w każdej chwili wyczyścić dane przeglądarki. Jeżeli przepisy mają zastosowanie, możesz zażądać dostępu, sprostowania, ograniczenia albo usunięcia danych oraz złożyć skargę do właściwego organu ochrony danych.",
                ),
                (
                    "Kontakt",
                    "W sprawach prywatności skontaktuj się z operatorem projektu przez repozytorium EvalForge w GitHub. Nie umieszczaj w publicznym zgłoszeniu wrażliwych danych osobowych.",
                ),
                (
                    "Zmiany",
                    "Polityka może zostać zaktualizowana po zmianie serwisu, hostingu lub zasad przetwarzania. Ostatnia aktualizacja: 5 sierpnia 2026 roku.",
                ),
            ],
        ),
        "terms": (
            "Warunki korzystania",
            [
                (
                    "Publiczna prezentacja",
                    "EvalForge jest obecnie bezpłatną interaktywną prezentacją produktu. Korzysta z deterministycznych wyników symulowanych i nie wywołuje API dostawców. Publiczna rejestracja, klucze dostawców i trwały zapis danych odwiedzających są wyłączone.",
                ),
                (
                    "Dozwolone korzystanie",
                    "Możesz przeglądać prezentację w celu oceny, nauki i zapoznania się z portfolio. Nie wolno zakłócać działania serwisu, omijać zabezpieczeń, szukać sekretów, przeciążać infrastruktury ani używać serwisu niezgodnie z prawem.",
                ),
                (
                    "Brak zastosowania produkcyjnego",
                    "Wyniki i przykładowe dane mają charakter ilustracyjny. Nie należy opierać na nich jako jedynej podstawie decyzji produkcyjnych, zakupowych, prawnych, finansowych ani krytycznych dla bezpieczeństwa.",
                ),
                (
                    "Dostępność i odpowiedzialność",
                    "Prezentacja jest udostępniana w aktualnie dostępnej postaci i może zostać zmieniona, wstrzymana albo usunięta. Nie gwarantujemy ciągłej dostępności, dokładności ani przydatności do określonego celu.",
                ),
                (
                    "Własność intelektualna",
                    "Kod źródłowy EvalForge jest dostępny na licencji MIT. Nazwy, usługi i znaki towarowe podmiotów trzecich pozostają własnością ich właścicieli.",
                ),
                (
                    "Usługi zewnętrzne",
                    "Odnośniki do GitHub, Render, Neon i innych dostawców prowadzą do niezależnych usług działających na podstawie własnych warunków i polityk.",
                ),
                (
                    "Zmiany i kontakt",
                    "Warunki mogą się zmieniać wraz z rozwojem projektu. Pytania można przekazywać przez repozytorium EvalForge w GitHub. Ostatnia aktualizacja: 5 sierpnia 2026 roku.",
                ),
            ],
        ),
    },
}


def _language() -> str:
    return str(app.storage.user.get("language", settings.default_language))


def _copy() -> dict[str, object]:
    return COPY.get(_language(), COPY["en"])


def _public_header() -> None:
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
            if settings.showcase_mode:
                ui.button(
                    str(copy["header_demo"]),
                    icon="play_arrow",
                    on_click=lambda: ui.navigate.to("/demo"),
                ).props("flat no-caps").classes("ef-public-sign-in")
            else:
                ui.button(str(copy["sign_in"]), on_click=lambda: ui.navigate.to("/login")).props(
                    "flat no-caps"
                ).classes("ef-public-sign-in")


def _footer() -> None:
    copy = _copy()
    with ui.element("footer").classes("ef-public-footer"):
        ui.label("EvalForge").classes("font-bold")
        with ui.row().classes("items-center gap-5 flex-wrap"):
            ui.link(str(copy["privacy"]), "/privacy")
            ui.link(str(copy["terms"]), "/terms")
            ui.link(
                str(copy["github"]),
                "https://github.com/mlynarskim/EvalForge",
                new_tab=True,
            )


def _page_shell(content: Callable[[], None]) -> None:
    apply_theme()
    ui.dark_mode(value=bool(app.storage.user.get("dark", False)))
    _public_header()
    content()
    _footer()


def register() -> None:
    @ui.page("/welcome")
    def landing_page() -> None:
        def content() -> None:
            copy = _copy()
            with ui.column().classes("ef-landing w-full"):
                with ui.element("section").classes("ef-hero"):
                    with ui.column().classes("ef-hero-copy"):
                        ui.label(str(copy["eyebrow"])).classes("ef-eyebrow")
                        ui.label(str(copy["hero_title"])).classes("ef-hero-title")
                        ui.label(str(copy["hero_body"])).classes("ef-hero-body")
                        with ui.row().classes("gap-3 flex-wrap mt-3"):
                            if settings.demo_mode:
                                ui.button(
                                    str(copy["demo"]),
                                    icon="play_arrow",
                                    on_click=lambda: ui.navigate.to("/demo"),
                                ).props("unelevated no-caps size=lg")
                            if not settings.showcase_mode:
                                ui.button(
                                    str(copy["sign_in"]),
                                    icon="login",
                                    on_click=lambda: ui.navigate.to("/login"),
                                ).props("outline no-caps size=lg")
                        ui.label(str(copy["demo_note"])).classes("ef-muted text-sm mt-2")
                    with ui.card().classes("ef-product-preview ef-card"):
                        ui.label("EvalForge").classes("text-lg font-bold")
                        ui.label("Model decision summary").classes("ef-muted text-sm")
                        with ui.element("div").classes("ef-preview-grid"):
                            for value, label in (
                                ("90%", "Quality"),
                                ("0.8 s", "Latency"),
                                ("€0.004", "Cost"),
                            ):
                                with ui.element("div").classes("ef-preview-stat"):
                                    ui.label(value).classes("text-2xl font-bold")
                                    ui.label(label).classes("ef-muted text-sm")
                        with ui.element("div").classes("ef-preview-result"):
                            ui.icon("verified", color="positive", size="28px")
                            with ui.column().classes("gap-0"):
                                ui.label("Recommended model").classes("text-xs ef-muted")
                                ui.label("Best quality to cost ratio").classes("font-semibold")

                with ui.element("section").classes("ef-public-section"):
                    ui.label(str(copy["value_title"])).classes("ef-section-title")
                    ui.label(str(copy["value_body"])).classes("ef-section-lead")
                    with ui.element("div").classes("ef-feature-grid"):
                        icons = ("science", "compare_arrows", "fact_check")
                        features = cast(list[tuple[str, str]], copy["features"])
                        for icon, (title, body) in zip(icons, features, strict=True):
                            with ui.card().classes("ef-feature-card ef-card"):
                                ui.icon(icon, color="primary", size="32px")
                                ui.label(title).classes("text-xl font-bold")
                                ui.label(body).classes("ef-muted leading-relaxed")

                with ui.element("section").classes("ef-public-section ef-how"):
                    ui.label(str(copy["how_title"])).classes("ef-section-title")
                    with ui.element("div").classes("ef-steps-grid"):
                        steps = cast(list[tuple[str, str]], copy["steps"])
                        for number, (title, body) in enumerate(steps, start=1):
                            with ui.element("div").classes("ef-public-step"):
                                ui.label(str(number)).classes("ef-step-number")
                                ui.label(title).classes("text-lg font-bold")
                                ui.label(body).classes("ef-muted")
                    ui.label(str(copy["built_with"])).classes("ef-muted text-center mt-6")

            _footer()

        apply_theme()
        ui.dark_mode(value=bool(app.storage.user.get("dark", False)))
        _public_header()
        content()

    def legal_page(kind: str) -> None:
        def content() -> None:
            title, sections = LEGAL.get(_language(), LEGAL["en"])[kind]
            with ui.column().classes("ef-legal"):
                ui.button(
                    str(_copy()["back"]),
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/welcome"),
                ).props("flat no-caps").classes("self-start")
                ui.label(title).classes("ef-legal-title")
                for heading, paragraph in sections:
                    with ui.element("section").classes("ef-legal-section"):
                        ui.label(heading).classes("text-xl font-bold")
                        ui.label(paragraph).classes("ef-legal-paragraph")

        _page_shell(content)

    @ui.page("/privacy")
    def privacy_page() -> None:
        legal_page("privacy")

    @ui.page("/terms")
    def terms_page() -> None:
        legal_page("terms")
