from __future__ import annotations

from dnd_llm.config import Settings


def test_settings_reads_model_cost_monitoring_env(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_INPUT_COST_PER_1M", "2.5")
    monkeypatch.setenv("MODEL_OUTPUT_COST_PER_1M", "10")
    monkeypatch.setenv("MODEL_COST_BUDGET", "0.25")
    monkeypatch.setenv("MODEL_COST_CURRENCY", "CNY")

    settings = Settings.from_env()

    assert settings.model_input_cost_per_million == 2.5
    assert settings.model_output_cost_per_million == 10.0
    assert settings.model_cost_budget == 0.25
    assert settings.model_cost_currency == "CNY"
