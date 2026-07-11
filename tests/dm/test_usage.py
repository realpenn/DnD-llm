from __future__ import annotations

import pytest

from dnd_llm.core.persistence import AuditLog
from dnd_llm.dm.usage import CostMonitor, ModelCostConfig, render_cost_report


def test_cost_monitor_groups_model_usage_and_budget(make_state) -> None:
    state = make_state()
    audit = AuditLog()
    audit.append(
        state,
        idempotency_key="model:dm",
        tool_name="dm.model_draft",
        model_id="dm-model",
        model_usage={"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
    )
    audit.append(
        state,
        idempotency_key="model:summary",
        tool_name="dm.summary",
        model_id="summary-model",
        model_usage={"prompt_tokens": 2000, "completion_tokens": 100, "total_tokens": 2100},
    )

    report = CostMonitor(
        ModelCostConfig(
            input_cost_per_million=2.0,
            output_cost_per_million=8.0,
            budget=0.01,
        )
    ).report(audit.events)

    assert report.prompt_tokens == 3000
    assert report.completion_tokens == 600
    assert report.total_tokens == 3600
    assert report.estimated_cost == pytest.approx(0.0108)
    assert report.budget_exceeded is True
    assert [item.model_id for item in report.by_model] == ["dm-model", "summary-model"]
    assert report.by_model[0].estimated_cost == pytest.approx(0.006)

    text = render_cost_report(report)
    assert "成本监控" in text
    assert "USD 0.010800" in text
    assert "108.0%" in text
    assert "已超出" in text


def test_cost_monitor_reports_unconfigured_pricing(make_state) -> None:
    state = make_state()
    audit = AuditLog()
    audit.append(
        state,
        idempotency_key="model:no-price",
        tool_name="dm.model_draft",
        model_id=None,
        model_usage={"prompt_tokens": 10, "completion_tokens": 5},
    )

    report = CostMonitor().report(audit.events)

    assert report.total_tokens == 15
    assert report.estimated_cost is None
    assert report.by_model[0].model_id == "unknown"
    assert "未配置单价" in render_cost_report(report)
