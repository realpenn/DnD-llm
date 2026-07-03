from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


def model_usage_from_response(response: dict[str, Any]) -> dict[str, int]:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return {}
    prompt_tokens = _int_usage(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _int_usage(usage, "completion_tokens", "output_tokens")
    total_tokens = _int_usage(usage, "total_tokens")
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens
    result = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    return {key: value for key, value in result.items() if value > 0}


def _int_usage(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if value is not None:
            return max(0, int(value))
    return 0


@dataclass(frozen=True)
class ModelCostConfig:
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    budget: float | None = None
    currency: str = "USD"

    @property
    def pricing_configured(self) -> bool:
        return self.input_cost_per_million is not None or self.output_cost_per_million is not None


@dataclass(frozen=True)
class ModelCostBreakdown:
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float | None


@dataclass(frozen=True)
class ModelCostReport:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float | None
    currency: str
    budget: float | None
    by_model: list[ModelCostBreakdown]

    @property
    def budget_ratio(self) -> float | None:
        if self.estimated_cost is None or self.budget is None or self.budget <= 0:
            return None
        return self.estimated_cost / self.budget

    @property
    def budget_exceeded(self) -> bool:
        return (
            self.estimated_cost is not None
            and self.budget is not None
            and self.budget > 0
            and self.estimated_cost >= self.budget
        )


class CostMonitor:
    def __init__(self, config: ModelCostConfig | None = None):
        self.config = config or ModelCostConfig()

    def report(self, events: Iterable[Any]) -> ModelCostReport:
        totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        by_model: dict[str, dict[str, int]] = {}
        for event in events:
            usage = getattr(event, "model_usage", {})
            if not isinstance(usage, dict) or not usage:
                continue
            model_id = str(getattr(event, "model_id", None) or "unknown")
            bucket = by_model.setdefault(
                model_id,
                {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            )
            prompt_tokens = _usage_value(usage, "prompt_tokens")
            completion_tokens = _usage_value(usage, "completion_tokens")
            total_tokens = _usage_value(usage, "total_tokens")
            if total_tokens == 0:
                total_tokens = prompt_tokens + completion_tokens
            for key, value in {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }.items():
                totals[key] += value
                bucket[key] += value

        breakdowns = [
            ModelCostBreakdown(
                model_id=model_id,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"],
                estimated_cost=self._estimate_cost(
                    usage["prompt_tokens"],
                    usage["completion_tokens"],
                ),
            )
            for model_id, usage in sorted(by_model.items())
        ]
        return ModelCostReport(
            prompt_tokens=totals["prompt_tokens"],
            completion_tokens=totals["completion_tokens"],
            total_tokens=totals["total_tokens"],
            estimated_cost=self._estimate_cost(
                totals["prompt_tokens"],
                totals["completion_tokens"],
            ),
            currency=self.config.currency,
            budget=self.config.budget,
            by_model=breakdowns,
        )

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float | None:
        if not self.config.pricing_configured:
            return None
        input_rate = self.config.input_cost_per_million or 0.0
        output_rate = self.config.output_cost_per_million or 0.0
        return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000


def render_cost_report(report: ModelCostReport) -> str:
    lines = [
        "成本监控：",
        (
            "模型用量："
            f"prompt={report.prompt_tokens} "
            f"completion={report.completion_tokens} "
            f"total={report.total_tokens} tokens"
        ),
    ]
    if report.estimated_cost is None:
        lines.append("估算成本：未配置单价（MODEL_INPUT_COST_PER_1M / MODEL_OUTPUT_COST_PER_1M）")
    else:
        lines.append(f"估算成本：{_money(report.estimated_cost, report.currency)}")
        if report.budget is not None:
            ratio = report.budget_ratio
            if ratio is None:
                lines.append(f"预算：{_money(report.budget, report.currency)}")
            else:
                status = "已超出" if report.budget_exceeded else "未超出"
                lines.append(
                    f"预算：{_money(report.budget, report.currency)}（{ratio:.1%}，{status}）"
                )
    if report.by_model:
        lines.append("模型明细：")
        for item in report.by_model:
            suffix = (
                ""
                if item.estimated_cost is None
                else f" cost={_money(item.estimated_cost, report.currency)}"
            )
            lines.append(
                f"- {item.model_id}: "
                f"prompt={item.prompt_tokens} "
                f"completion={item.completion_tokens} "
                f"total={item.total_tokens}{suffix}"
            )
    return "\n".join(lines)


def _usage_value(usage: dict[str, Any], key: str) -> int:
    value = usage.get(key)
    return max(0, int(value)) if value is not None else 0


def _money(value: float, currency: str) -> str:
    return f"{currency} {value:.6f}"
