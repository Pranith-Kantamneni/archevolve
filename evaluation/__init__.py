from __future__ import annotations

from typing import Tuple, Dict, Any

from .cost_evaluator import CostEvaluator, EvaluatorResult as CostResult
from .security_evaluator import SecurityEvaluator, EvaluatorResult as SecurityResult
from .reliability_evaluator import ReliabilityEvaluator, EvaluatorResult as ReliabilityResult
from .performance_evaluator import PerformanceEvaluator, EvaluatorResult as PerformanceResult
from .scalability_evaluator import ScalabilityEvaluator, EvaluatorResult as ScalabilityResult


class FitnessResult:
    """Combined fitness result from all evaluators."""

    def __init__(
        self,
        cost: float,
        security: float,
        reliability: float,
        performance: float,
        scalability: float,
        overall: float,
        cost_reasoning: str = "",
        security_reasoning: str = "",
        reliability_reasoning: str = "",
        performance_reasoning: str = "",
        scalability_reasoning: str = "",
        evaluator_results: Dict[str, Any] | None = None,
    ):
        self.cost = cost
        self.security = security
        self.reliability = reliability
        self.performance = performance
        self.scalability = scalability
        self.overall = overall

        self.cost_reasoning = cost_reasoning
        self.security_reasoning = security_reasoning
        self.reliability_reasoning = reliability_reasoning
        self.performance_reasoning = performance_reasoning
        self.scalability_reasoning = scalability_reasoning

        self.evaluator_results = evaluator_results or {}

    def __str__(self) -> str:
        lines = [
            f"Cost: {self.cost:.1f}",
            f"Security: {self.security:.1f}",
            f"Reliability: {self.reliability:.1f}",
            f"Performance: {self.performance:.1f}",
            f"Scalability: {self.scalability:.1f}",
            f"Fitness: {self.overall:.1f}",
        ]
        return "\n".join(lines)


def _get_components(architecture: object) -> list:
    """Extract components list from architecture, handling both Pydantic models and dicts."""
    if hasattr(architecture, "components"):
        comps = architecture.components
        if isinstance(comps, list):
            return comps
    if isinstance(architecture, dict):
        comps = architecture.get("components", [])
        if isinstance(comps, list):
            return comps
    return []


def evaluate_architecture(
    architecture: object,
) -> FitnessResult:
    """Evaluate an architecture across all objectives and compute fitness."""
    # Cost evaluation
    cost_eval = CostEvaluator()
    cost_result = cost_eval.evaluate(architecture)
    cost = cost_result.score

    # Security evaluation
    sec_eval = SecurityEvaluator()
    sec_result = sec_eval.evaluate(architecture)
    security = sec_result.score

    # Reliability evaluation
    rel_eval = ReliabilityEvaluator()
    rel_result = rel_eval.evaluate(architecture)
    reliability = rel_result.score

    # Performance evaluation
    perf_eval = PerformanceEvaluator()
    perf_result = perf_eval.evaluate(architecture)
    performance = perf_result.score

    # Scalability evaluation
    scal_eval = ScalabilityEvaluator()
    scal_result = scal_eval.evaluate(architecture)
    scalability = scal_result.score

    # Weighted fitness (equal weights by default)
    overall = (
        0.20 * cost
        + 0.20 * security
        + 0.20 * reliability
        + 0.20 * performance
        + 0.20 * scalability
    )

    eval_results = {
        "cost": cost_result,
        "security": sec_result,
        "reliability": rel_result,
        "performance": perf_result,
        "scalability": scal_result,
    }

    return FitnessResult(
        cost=cost,
        security=security,
        reliability=reliability,
        performance=performance,
        scalability=scalability,
        overall=overall,
        cost_reasoning=cost_result.reasoning,
        security_reasoning=sec_result.reasoning,
        reliability_reasoning=rel_result.reasoning,
        performance_reasoning=perf_result.reasoning,
        scalability_reasoning=scal_result.reasoning,
        evaluator_results=eval_results,
    )