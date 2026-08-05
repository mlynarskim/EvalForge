from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DemoCase:
    name: dict[str, str]
    input_text: dict[str, str]
    expected: dict[str, Any]


@dataclass(frozen=True)
class DemoScenario:
    key: str
    title: dict[str, str]
    description: dict[str, str]
    prompt: dict[str, str]
    cases: tuple[DemoCase, ...]


@dataclass(frozen=True)
class DemoModel:
    key: str
    name: str
    provider: str
    description: dict[str, str]
    quality_base: float
    latency_base_ms: int
    total_cost_eur: float


@dataclass(frozen=True)
class DemoCaseResult:
    case_name: str
    input_text: str
    expected: dict[str, Any]
    answer: str
    quality: float
    passed: bool
    json_valid: bool
    latency_ms: int
    tokens: int
    cost_eur: float


@dataclass(frozen=True)
class DemoModelResult:
    model_key: str
    model_name: str
    provider: str
    quality: float
    pass_rate: float
    json_validity: float
    average_latency_ms: int
    total_tokens: int
    total_cost_eur: float
    weighted_score: float
    cases: tuple[DemoCaseResult, ...]


@dataclass(frozen=True)
class DemoRun:
    scenario_key: str
    scenario_title: str
    prompt: str
    simulated: bool
    recommendation_key: str
    recommendation_reason: str
    results: tuple[DemoModelResult, ...]


SCENARIOS: dict[str, DemoScenario] = {
    "support": DemoScenario(
        key="support",
        title={"en": "Customer support triage", "pl": "Klasyfikacja zgłoszeń klienta"},
        description={
            "en": "Classify incoming tickets and identify cases that require a human.",
            "pl": "Klasyfikuj zgłoszenia i wykrywaj sprawy wymagające udziału człowieka.",
        },
        prompt={
            "en": "Classify the customer ticket. Return valid JSON with category, priority, summary and requires_human.",
            "pl": "Sklasyfikuj zgłoszenie klienta. Zwróć poprawny JSON z polami category, priority, summary oraz requires_human.",
        },
        cases=(
            DemoCase(
                name={"en": "Late delivery", "pl": "Opóźniona dostawa"},
                input_text={
                    "en": "My parcel is five days late and tracking has not changed.",
                    "pl": "Moja przesyłka jest spóźniona o pięć dni, a status się nie zmienia.",
                },
                expected={
                    "category": "complaint",
                    "priority": "high",
                    "summary": "Delayed parcel with stale tracking",
                    "requires_human": True,
                },
            ),
            DemoCase(
                name={"en": "Invoice request", "pl": "Prośba o fakturę"},
                input_text={
                    "en": "Where can I download an invoice for order 1842?",
                    "pl": "Gdzie mogę pobrać fakturę do zamówienia 1842?",
                },
                expected={
                    "category": "question",
                    "priority": "low",
                    "summary": "Customer needs an invoice",
                    "requires_human": False,
                },
            ),
            DemoCase(
                name={"en": "Duplicate charge", "pl": "Podwójne obciążenie"},
                input_text={
                    "en": "I was charged twice. Please return the second payment.",
                    "pl": "Płatność została pobrana dwa razy. Proszę zwrócić drugą kwotę.",
                },
                expected={
                    "category": "refund",
                    "priority": "high",
                    "summary": "Duplicate payment requires refund",
                    "requires_human": True,
                },
            ),
            DemoCase(
                name={"en": "Application crash", "pl": "Awaria aplikacji"},
                input_text={
                    "en": "The desktop application closes whenever I upload a PDF.",
                    "pl": "Aplikacja zamyka się za każdym razem, gdy przesyłam plik PDF.",
                },
                expected={
                    "category": "technical_issue",
                    "priority": "high",
                    "summary": "Application crashes during PDF upload",
                    "requires_human": True,
                },
            ),
            DemoCase(
                name={"en": "Cancellation", "pl": "Rezygnacja"},
                input_text={
                    "en": "Please cancel my subscription at the end of this month.",
                    "pl": "Proszę anulować subskrypcję z końcem tego miesiąca.",
                },
                expected={
                    "category": "other",
                    "priority": "medium",
                    "summary": "Subscription cancellation request",
                    "requires_human": False,
                },
            ),
        ),
    ),
    "invoice": DemoScenario(
        key="invoice",
        title={"en": "Invoice extraction", "pl": "Ekstrakcja danych z faktur"},
        description={
            "en": "Extract structured accounting fields from short invoice fragments.",
            "pl": "Wyodrębniaj ustrukturyzowane dane księgowe z fragmentów faktur.",
        },
        prompt={
            "en": "Extract vendor, invoice_number, currency, net_amount and total_amount. Return valid JSON only.",
            "pl": "Wyodrębnij vendor, invoice_number, currency, net_amount oraz total_amount. Zwróć wyłącznie poprawny JSON.",
        },
        cases=(
            DemoCase(
                name={"en": "Software license", "pl": "Licencja oprogramowania"},
                input_text={
                    "en": "Northstar Cloud, invoice NS 1042, net EUR 120.00, total EUR 147.60.",
                    "pl": "Northstar Cloud, faktura NS 1042, netto 120,00 EUR, brutto 147,60 EUR.",
                },
                expected={
                    "vendor": "Northstar Cloud",
                    "invoice_number": "NS 1042",
                    "currency": "EUR",
                    "net_amount": 120.0,
                    "total_amount": 147.6,
                },
            ),
            DemoCase(
                name={"en": "Office supplies", "pl": "Materiały biurowe"},
                input_text={
                    "en": "Paperline Ltd. INV 7781. Net 460.00 PLN. Amount due 565.80 PLN.",
                    "pl": "Paperline sp. z o.o. FV 7781. Netto 460,00 PLN. Do zapłaty 565,80 PLN.",
                },
                expected={
                    "vendor": "Paperline",
                    "invoice_number": "7781",
                    "currency": "PLN",
                    "net_amount": 460.0,
                    "total_amount": 565.8,
                },
            ),
            DemoCase(
                name={"en": "Consulting", "pl": "Konsulting"},
                input_text={
                    "en": "Brightpath Consulting, BP 2026 88, subtotal USD 900, total USD 900.",
                    "pl": "Brightpath Consulting, BP 2026 88, netto 900 USD, razem 900 USD.",
                },
                expected={
                    "vendor": "Brightpath Consulting",
                    "invoice_number": "BP 2026 88",
                    "currency": "USD",
                    "net_amount": 900.0,
                    "total_amount": 900.0,
                },
            ),
            DemoCase(
                name={"en": "Hosting", "pl": "Hosting"},
                input_text={
                    "en": "Compute Harbor CH 441. Services 74.50 EUR plus tax. Total 91.64 EUR.",
                    "pl": "Compute Harbor CH 441. Usługi 74,50 EUR plus podatek. Razem 91,64 EUR.",
                },
                expected={
                    "vendor": "Compute Harbor",
                    "invoice_number": "CH 441",
                    "currency": "EUR",
                    "net_amount": 74.5,
                    "total_amount": 91.64,
                },
            ),
            DemoCase(
                name={"en": "Training", "pl": "Szkolenie"},
                input_text={
                    "en": "Learnworks invoice LW 19. Net amount 2500 PLN, gross amount 3075 PLN.",
                    "pl": "Learnworks faktura LW 19. Kwota netto 2500 PLN, brutto 3075 PLN.",
                },
                expected={
                    "vendor": "Learnworks",
                    "invoice_number": "LW 19",
                    "currency": "PLN",
                    "net_amount": 2500.0,
                    "total_amount": 3075.0,
                },
            ),
        ),
    ),
    "feedback": DemoScenario(
        key="feedback",
        title={"en": "Product feedback analysis", "pl": "Analiza opinii o produkcie"},
        description={
            "en": "Summarize feedback, detect sentiment and identify the main topic.",
            "pl": "Podsumowuj opinie, rozpoznawaj sentyment i główny temat.",
        },
        prompt={
            "en": "Analyze the feedback. Return JSON with sentiment, topic, summary and action_required.",
            "pl": "Przeanalizuj opinię. Zwróć JSON z polami sentiment, topic, summary oraz action_required.",
        },
        cases=(
            DemoCase(
                name={"en": "Slow export", "pl": "Powolny eksport"},
                input_text={
                    "en": "The dashboard is clear, but exporting larger reports takes several minutes.",
                    "pl": "Pulpit jest czytelny, ale eksport większych raportów trwa kilka minut.",
                },
                expected={
                    "sentiment": "mixed",
                    "topic": "performance",
                    "summary": "Clear dashboard with slow report exports",
                    "action_required": True,
                },
            ),
            DemoCase(
                name={"en": "Great onboarding", "pl": "Dobre wdrożenie"},
                input_text={
                    "en": "The guided setup helped our team run the first evaluation quickly.",
                    "pl": "Przewodnik pomógł zespołowi szybko uruchomić pierwszą ewaluację.",
                },
                expected={
                    "sentiment": "positive",
                    "topic": "onboarding",
                    "summary": "Guided setup accelerates first evaluation",
                    "action_required": False,
                },
            ),
            DemoCase(
                name={"en": "Missing filters", "pl": "Brak filtrów"},
                input_text={
                    "en": "Results are useful, although I need filters by provider and date.",
                    "pl": "Wyniki są przydatne, ale potrzebuję filtrów według dostawcy i daty.",
                },
                expected={
                    "sentiment": "mixed",
                    "topic": "reporting",
                    "summary": "Results need provider and date filters",
                    "action_required": True,
                },
            ),
            DemoCase(
                name={"en": "Unexpected cost", "pl": "Nieoczekiwany koszt"},
                input_text={
                    "en": "The experiment exceeded the estimate and I could not see why.",
                    "pl": "Eksperyment przekroczył szacunek i nie było wiadomo dlaczego.",
                },
                expected={
                    "sentiment": "negative",
                    "topic": "cost",
                    "summary": "Experiment cost exceeded estimate without explanation",
                    "action_required": True,
                },
            ),
            DemoCase(
                name={"en": "Easy comparison", "pl": "Łatwe porównanie"},
                input_text={
                    "en": "Side by side model answers made the selection meeting much easier.",
                    "pl": "Odpowiedzi modeli obok siebie znacznie ułatwiły spotkanie decyzyjne.",
                },
                expected={
                    "sentiment": "positive",
                    "topic": "comparison",
                    "summary": "Side by side answers simplify model selection",
                    "action_required": False,
                },
            ),
        ),
    ),
}


MODELS: dict[str, DemoModel] = {
    "atlas": DemoModel(
        key="atlas",
        name="Atlas Reasoning",
        provider="Provider A",
        description={
            "en": "Highest answer quality with slower responses and higher cost.",
            "pl": "Najwyższa jakość przy wolniejszych odpowiedziach i wyższym koszcie.",
        },
        quality_base=0.97,
        latency_base_ms=1280,
        total_cost_eur=0.014,
    ),
    "pulse": DemoModel(
        key="pulse",
        name="Pulse Balanced",
        provider="Provider B",
        description={
            "en": "Strong quality, moderate latency and a balanced cost profile.",
            "pl": "Wysoka jakość, umiarkowany czas oraz zrównoważony koszt.",
        },
        quality_base=0.92,
        latency_base_ms=760,
        total_cost_eur=0.006,
    ),
    "nova": DemoModel(
        key="nova",
        name="Nova Fast",
        provider="Provider C",
        description={
            "en": "Fastest and cheapest, with less reliable structured output.",
            "pl": "Najszybszy i najtańszy, ale mniej niezawodny dla danych strukturalnych.",
        },
        quality_base=0.84,
        latency_base_ms=410,
        total_cost_eur=0.0025,
    ),
}


def localized(values: dict[str, str], language: str) -> str:
    return values.get(language, values["en"])


def _degraded_answer(scenario_key: str, expected: dict[str, Any]) -> dict[str, Any]:
    answer = dict(expected)
    if scenario_key == "support":
        answer["priority"] = "low"
        answer["requires_human"] = False
    elif scenario_key == "invoice":
        answer["total_amount"] = answer.get("net_amount")
    else:
        answer["sentiment"] = "neutral"
        answer["action_required"] = False
    return answer


def simulate_demo(
    scenario_key: str,
    model_keys: list[str],
    prompt: str,
    language: str = "en",
) -> DemoRun:
    if scenario_key not in SCENARIOS:
        raise ValueError("Unknown demonstration scenario")
    if len(model_keys) < 2:
        raise ValueError("Select at least two models")
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    scenario = SCENARIOS[scenario_key]
    offsets = (-0.01, 0.01, -0.04, 0.0, -0.03)
    provisional: list[DemoModelResult] = []
    for model_key in model_keys:
        if model_key not in MODELS:
            raise ValueError("Unknown demonstration model")
        model = MODELS[model_key]
        case_results: list[DemoCaseResult] = []
        for index, case in enumerate(scenario.cases):
            quality = max(0.0, min(1.0, model.quality_base + offsets[index]))
            passed = quality >= 0.83
            json_valid = not (model.key == "nova" and index == len(scenario.cases) - 1)
            output = (
                dict(case.expected) if passed else _degraded_answer(scenario.key, case.expected)
            )
            answer = json.dumps(output, ensure_ascii=False, indent=2)
            if not json_valid:
                answer = answer[:-2]
                passed = False
            case_results.append(
                DemoCaseResult(
                    case_name=localized(case.name, language),
                    input_text=localized(case.input_text, language),
                    expected=case.expected,
                    answer=answer,
                    quality=round(quality, 3),
                    passed=passed,
                    json_valid=json_valid,
                    latency_ms=model.latency_base_ms + index * 37,
                    tokens=112 + index * 9 + len(prompt) // 12,
                    cost_eur=round(model.total_cost_eur / len(scenario.cases), 5),
                )
            )
        count = len(case_results)
        provisional.append(
            DemoModelResult(
                model_key=model.key,
                model_name=model.name,
                provider=model.provider,
                quality=round(sum(item.quality for item in case_results) / count, 3),
                pass_rate=round(sum(item.passed for item in case_results) / count, 3),
                json_validity=round(sum(item.json_valid for item in case_results) / count, 3),
                average_latency_ms=round(sum(item.latency_ms for item in case_results) / count),
                total_tokens=sum(item.tokens for item in case_results),
                total_cost_eur=round(sum(item.cost_eur for item in case_results), 5),
                weighted_score=0.0,
                cases=tuple(case_results),
            )
        )
    max_cost = max(item.total_cost_eur for item in provisional) or 1
    max_latency = max(item.average_latency_ms for item in provisional) or 1
    results = tuple(
        DemoModelResult(
            **{
                **asdict(item),
                "weighted_score": round(
                    item.quality * 0.55
                    + item.pass_rate * 0.20
                    + (1 - item.total_cost_eur / max_cost) * 0.10
                    + (1 - item.average_latency_ms / max_latency) * 0.15,
                    3,
                ),
                "cases": item.cases,
            }
        )
        for item in provisional
    )
    recommended = max(results, key=lambda item: item.weighted_score)
    reasons = {
        "en": f"{recommended.model_name} offers the strongest weighted balance of quality, reliability, latency and cost for this scenario.",
        "pl": f"{recommended.model_name} zapewnia najlepszy ważony kompromis jakości, niezawodności, czasu i kosztu dla tego scenariusza.",
    }
    return DemoRun(
        scenario_key=scenario.key,
        scenario_title=localized(scenario.title, language),
        prompt=prompt.strip(),
        simulated=True,
        recommendation_key=recommended.model_key,
        recommendation_reason=reasons.get(language, reasons["en"]),
        results=results,
    )


def demo_report(run: DemoRun) -> dict[str, Any]:
    return {
        "product": "EvalForge",
        "report_type": "simulated_demonstration",
        "simulated": True,
        "scenario": run.scenario_title,
        "prompt": run.prompt,
        "recommendation": {
            "model_key": run.recommendation_key,
            "reason": run.recommendation_reason,
        },
        "models": [asdict(result) for result in run.results],
        "notice": "No provider API was called and no visitor data was persisted.",
    }
