from __future__ import annotations

from dnd_llm.config import Settings
from dnd_llm.resources import bundled_rules_data_dir


def test_default_rules_data_dir_resolves_bundled_distribution_data(monkeypatch) -> None:
    monkeypatch.delenv("RULES_DATA_DIR", raising=False)

    settings = Settings.from_env()

    assert settings.rules_data_dir == str(bundled_rules_data_dir())
    assert (bundled_rules_data_dir() / "campaigns" / "starter" / "pack.json").is_file()


def test_external_rules_data_dir_overrides_bundled_data(monkeypatch, tmp_path) -> None:
    external = tmp_path / "rules_data"
    monkeypatch.setenv("RULES_DATA_DIR", str(external))

    assert Settings.from_env().rules_data_dir == str(external)


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
