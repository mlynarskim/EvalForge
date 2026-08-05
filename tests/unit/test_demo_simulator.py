from app.services.demo_simulator import MODELS, SCENARIOS, demo_report, simulate_demo


def test_demo_simulation_compares_models_without_external_state() -> None:
    run = simulate_demo(
        scenario_key="support",
        model_keys=list(MODELS),
        prompt=SCENARIOS["support"].prompt["en"],
        language="en",
    )

    assert run.simulated is True
    assert len(run.results) == 3
    assert all(len(result.cases) == 5 for result in run.results)
    assert run.recommendation_key == "pulse"
    assert all(result.total_cost_eur > 0 for result in run.results)
    assert any(not case.passed for result in run.results for case in result.cases)


def test_demo_simulation_is_deterministic_and_localized() -> None:
    first = simulate_demo("invoice", ["atlas", "pulse"], SCENARIOS["invoice"].prompt["pl"], "pl")
    second = simulate_demo("invoice", ["atlas", "pulse"], SCENARIOS["invoice"].prompt["pl"], "pl")

    assert first == second
    assert first.scenario_title == "Ekstrakcja danych z faktur"
    assert "najlepszy ważony kompromis" in first.recommendation_reason


def test_demo_report_is_explicitly_simulated() -> None:
    run = simulate_demo("feedback", ["atlas", "pulse", "nova"], SCENARIOS["feedback"].prompt["en"])
    report = demo_report(run)

    assert report["simulated"] is True
    assert report["report_type"] == "simulated_demonstration"
    assert "No provider API was called" in report["notice"]
