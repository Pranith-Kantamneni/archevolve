from __future__ import annotations

from typing import Any, Dict, Optional

from .cost_evaluator import CostEvaluator
from .security_evaluator import SecurityEvaluator
from .reliability_evaluator import ReliabilityEvaluator
from .performance_evaluator import PerformanceEvaluator
from .scalability_evaluator import ScalabilityEvaluator
from .domain_params import PARAM_DEFS, blend_overall, blended_weights, evaluate_domain_params
from .scoring import CORE_DIMENSIONS, ScoringContext, grade_for, resolve_weights


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
        breakdowns: Dict[str, Dict[str, float]] | None = None,
        grades: Dict[str, str] | None = None,
        weights: Dict[str, float] | None = None,
        weight_profile: str = "default",
        domain_params: Dict[str, Dict[str, Any]] | None = None,
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
        self.breakdowns = breakdowns or {}
        self.grades = grades or {}
        self.weights = weights or {d: 0.2 for d in CORE_DIMENSIONS}
        self.weight_profile = weight_profile
        self.domain_params = domain_params or {}

    def __str__(self) -> str:
        lines = [
            f"Cost: {self.cost:.1f} ({self.grades.get('cost', '-')})",
            f"Security: {self.security:.1f} ({self.grades.get('security', '-')})",
            f"Reliability: {self.reliability:.1f} ({self.grades.get('reliability', '-')})",
            f"Performance: {self.performance:.1f} ({self.grades.get('performance', '-')})",
            f"Scalability: {self.scalability:.1f} ({self.grades.get('scalability', '-')})",
            f"Fitness: {self.overall:.1f} [{self.weight_profile}]",
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
    context: Any = None,
    weights: Optional[Dict[str, float]] = None,
    application_type: str = "",
) -> FitnessResult:
    """Evaluate an architecture across all objectives and compute fitness.

    Args:
        architecture: Architecture model instance or dict.
        context: ParsedRequirement / StructuredRequirements / dict / ScoringContext
            used to condition thresholds.  ``None`` uses neutral defaults.
        weights: Optional explicit per-dimension weights (need not sum to 1;
            they are normalized).  ``None`` resolves application-aware weights.
        application_type: Used for weight-profile detection when the context
            does not carry it.
    """
    if isinstance(context, ScoringContext):
        ctx = context
    else:
        ctx = ScoringContext.from_any(context, application_type=application_type)
    if not ctx.application_type and application_type:
        ctx.application_type = application_type

    cost_result = CostEvaluator().evaluate(architecture, ctx)
    sec_result = SecurityEvaluator().evaluate(architecture, ctx)
    rel_result = ReliabilityEvaluator().evaluate(architecture, ctx)
    perf_result = PerformanceEvaluator().evaluate(architecture, ctx)
    scal_result = ScalabilityEvaluator().evaluate(architecture, ctx)

    resolved = resolve_weights(ctx.application_type, ctx, overrides=weights)
    w = resolved["weights"]
    core_overall = (
        w.get("cost", 0.2) * cost_result.score
        + w.get("security", 0.2) * sec_result.score
        + w.get("reliability", 0.2) * rel_result.score
        + w.get("performance", 0.2) * perf_result.score
        + w.get("scalability", 0.2) * scal_result.score
    )

    eval_results = {
        "cost": cost_result,
        "security": sec_result,
        "reliability": rel_result,
        "performance": perf_result,
        "scalability": scal_result,
    }

    # Domain-specific parameters (innovative layer): evaluated only when the
    # application domain defines them; blended at EXTRA_SHARE into overall.
    extras = evaluate_domain_params(architecture, ctx)
    overall = blend_overall(core_overall, extras)
    domain_params = {
        name: {
            "label": PARAM_DEFS[name]["label"],
            "score": round(ds.score, 2),
            "grade": ds.grade,
            "breakdown": dict(ds.breakdown),
            "strengths": list(ds.strengths),
            "weaknesses": list(ds.weaknesses),
            "reason": ds.reason,
        }
        for name, ds in extras.items()
    }

    return FitnessResult(
        cost=cost_result.score,
        security=sec_result.score,
        reliability=rel_result.score,
        performance=perf_result.score,
        scalability=scal_result.score,
        overall=overall,
        cost_reasoning=cost_result.reasoning,
        security_reasoning=sec_result.reasoning,
        reliability_reasoning=rel_result.reasoning,
        performance_reasoning=perf_result.reasoning,
        scalability_reasoning=scal_result.reasoning,
        evaluator_results=eval_results,
        breakdowns={k: dict(v.breakdown) for k, v in eval_results.items()},
        grades={k: v.grade for k, v in eval_results.items()},
        weights=blended_weights({k: round(float(w.get(k, 0.0)), 4) for k in CORE_DIMENSIONS}, extras),
        weight_profile=resolved["profile"] + ("+domain" if extras else ""),
        domain_params=domain_params,
    )
