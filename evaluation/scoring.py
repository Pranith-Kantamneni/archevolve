"""Production-grade scoring foundation for ARCHEVOLVE.

Design principles (replaces the old "start at 100 / start at 50 and add/subtract"
heuristics that saturated at 100 for almost every candidate):

1. **Bottom-up earned points (0 -> 100).**  Every dimension starts at 0 and earns
   points through graded sub-criteria.  A perfect 100 requires *all* sub-criteria
   to be fully satisfied, which is intentionally rare.
2. **Requirement-conditioned.**  Thresholds scale with the parsed requirements
   (expected users, latency SLA, availability target, security level, budget,
   compliance, scalability type) and with the application domain, so the same
   architecture scores differently for a banking system vs. a chat app.
3. **Continuous, not binary.**  Wherever possible we use smooth curves
   (exponential decay, logistic) instead of cliff-edge if/else bonuses, so
   small architectural differences produce small score differences.
4. **Transparent.**  Every score ships with a per-criterion ``breakdown``
   (earned / max), a letter ``grade`` and human-readable strengths/weaknesses.
5. **Extensible.**  New quality dimensions are added by writing one evaluator
   module and registering it in :data:`DIMENSION_REGISTRY` -- no changes to
   the fitness engine, agents or UI data contract are required beyond the
   registry entry.

Score contract: every dimension score is in ``[0, 100]`` (higher is better),
overall fitness is a convex combination of dimensions (weights sum to 1.0).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Score container
# ---------------------------------------------------------------------------

#: Heuristic ceiling: static structural analysis can never verify runtime
#: truth (live mTLS, key rotation, chaos drills, pentests), so no parameter
#: may ever read 100/100.  The top band is reserved for production-verified
#: systems.  Enforced centrally in DimensionScore and EvaluatorResult.
HEURISTIC_CEILING = 97.0


def apply_ceiling(score: float) -> float:
    """Clamp a raw 0-100 rubric score to the heuristic ceiling."""
    return float(max(0.0, min(HEURISTIC_CEILING, score)))


@dataclass
class DimensionScore:
    """Result of scoring a single quality dimension."""

    score: float
    breakdown: Dict[str, float] = field(default_factory=dict)  # criterion -> earned pts
    max_breakdown: Dict[str, float] = field(default_factory=dict)  # criterion -> max pts
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    reason: str = ""
    grade: str = ""

    def __post_init__(self) -> None:
        self.score = apply_ceiling(self.score)
        if not self.grade:
            self.grade = grade_for(self.score)


def grade_for(score: float) -> str:
    """Letter grade for a 0-100 score (production-style rubric bands)."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Scoring context (requirement-conditioned thresholds)
# ---------------------------------------------------------------------------


@dataclass
class ScoringContext:
    """Normalized requirement signals that condition every evaluator."""

    application_type: str = ""
    expected_users: int = 1000
    max_latency_ms: Optional[float] = None
    availability_pct: Optional[float] = None
    security_level: str = "medium"  # low | medium | high
    scalability_type: Optional[str] = None
    cost_sensitive: bool = False
    max_monthly_cost: Optional[float] = None
    compliance: List[str] = field(default_factory=list)
    deployment_env: Optional[str] = None
    authentication_required: bool = True

    @classmethod
    def from_any(cls, obj: Any, application_type: str = "") -> "ScoringContext":
        """Build a context from ParsedRequirement / StructuredRequirements / dict / None."""
        if obj is None:
            return cls(application_type=application_type or "")
        get = None
        if isinstance(obj, dict):
            get = obj.get
            app = obj.get("application_type", application_type) or application_type
            return cls(
                application_type=str(app or ""),
                expected_users=int(obj.get("expected_users") or 1000),
                max_latency_ms=obj.get("max_latency_ms"),
                availability_pct=obj.get("availability_percentage"),
                security_level=str(obj.get("security_level") or "medium").lower(),
                scalability_type=obj.get("scalability_type"),
                cost_sensitive=bool(obj.get("cost_sensitive", False)),
                max_monthly_cost=obj.get("max_monthly_cost") or obj.get("max_budget"),
                compliance=list(obj.get("compliance_requirements") or obj.get("compliance") or []),
                deployment_env=obj.get("deployment_environment") or obj.get("deployment_env"),
                authentication_required=bool(obj.get("authentication_required", True)),
            )
        # Pydantic-style objects
        def _g(name: str, default: Any = None) -> Any:
            return getattr(obj, name, default) if hasattr(obj, name) else default

        app = _g("application_type", application_type) or application_type
        return cls(
            application_type=str(app or ""),
            expected_users=int(_g("expected_users", 1000) or 1000),
            max_latency_ms=_g("max_latency_ms", None),
            availability_pct=_g("availability_percentage", None),
            security_level=str(_g("security_level", "medium") or "medium").lower(),
            scalability_type=_g("scalability_type", None),
            cost_sensitive=bool(_g("cost_sensitive", False)),
            max_monthly_cost=_g("max_monthly_cost", None),
            compliance=list(_g("compliance_requirements", []) or []),
            deployment_env=_g("deployment_environment", None),
            authentication_required=bool(_g("authentication_required", True)),
        )

    @property
    def scale_tier(self) -> str:
        if self.expected_users >= 1_000_000:
            return "hyperscale"
        if self.expected_users >= 100_000:
            return "large"
        if self.expected_users >= 10_000:
            return "medium"
        return "small"

    @property
    def latency_sla_ms(self) -> float:
        return float(self.max_latency_ms) if self.max_latency_ms else 200.0

    @property
    def availability_target(self) -> float:
        return float(self.availability_pct) if self.availability_pct else 99.9


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Indicative managed-service monthly cost model (USD) used for *relative*
# cost-efficiency grading -- not a billing quote.  Values are deliberately
# coarse so rankings are stable across component renames.
UNIT_MONTHLY_COST: Dict[str, float] = {
    "gateway": 60.0,
    "load balancer": 60.0,
    "service": 160.0,
    "application": 220.0,
    "compute": 180.0,
    "database": 420.0,
    "datastore": 260.0,
    "cdn": 90.0,
    "cache": 140.0,
    "messaging": 170.0,
    "realtime": 150.0,
    "security": 90.0,
    "client": 0.0,
    "other": 120.0,
}

MANAGED_PREMIUM = 1.35  # managed services cost ~35% more than self-hosted


def estimate_monthly_cost(components: List[Any]) -> float:
    """Rough monthly infrastructure estimate for grading (USD)."""
    total = 0.0
    for c in components:
        ctype = getattr(c, "type", "other") or "other"
        key = ctype.lower() if isinstance(ctype, str) else "other"
        unit = UNIT_MONTHLY_COST.get(key, UNIT_MONTHLY_COST["other"])
        qty = max(1, int(getattr(c, "quantity", 1) or 1))
        managed = bool(getattr(c, "managed", False))
        total += unit * qty * (MANAGED_PREMIUM if managed else 1.0)
    return round(total, 2)


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def smooth_benefit(x: float, knee: float, steepness: float = 1.6) -> float:
    """Diminishing-returns curve: 0 at x<=0, ->1 as x grows past knee."""
    if x <= 0:
        return 0.0
    return 1.0 - math.exp(-((x / max(knee, 1e-9)) ** steepness))


def has_type(components: List[Any], *types: str) -> bool:
    wanted = {t.lower() for t in types}
    return any(str(getattr(c, "type", "")).lower() in wanted for c in components)


def count_type(components: List[Any], *types: str) -> int:
    wanted = {t.lower() for t in types}
    return sum(1 for c in components if str(getattr(c, "type", "")).lower() in wanted)


def has_name_like(components: List[Any], *keywords: str) -> bool:
    names = [str(getattr(c, "name", "")).lower() for c in components]
    return any(kw.lower() in n for n in names for kw in keywords)


# ---------------------------------------------------------------------------
# Application-aware weights
# ---------------------------------------------------------------------------

CORE_DIMENSIONS = ["cost", "security", "reliability", "performance", "scalability"]

# Base profiles per application domain.  Each row sums to 1.0.
DOMAIN_WEIGHT_PROFILES: Dict[str, Dict[str, float]] = {
    "default": {"cost": 0.20, "security": 0.20, "reliability": 0.20, "performance": 0.20, "scalability": 0.20},
    "banking": {"cost": 0.10, "security": 0.30, "reliability": 0.24, "performance": 0.16, "scalability": 0.20},
    "finance": {"cost": 0.10, "security": 0.30, "reliability": 0.24, "performance": 0.16, "scalability": 0.20},
    "healthcare": {"cost": 0.12, "security": 0.28, "reliability": 0.24, "performance": 0.16, "scalability": 0.20},
    "chat": {"cost": 0.12, "security": 0.14, "reliability": 0.20, "performance": 0.28, "scalability": 0.26},
    "messaging": {"cost": 0.12, "security": 0.14, "reliability": 0.20, "performance": 0.28, "scalability": 0.26},
    "gaming": {"cost": 0.12, "security": 0.12, "reliability": 0.20, "performance": 0.30, "scalability": 0.26},
    "streaming": {"cost": 0.12, "security": 0.12, "reliability": 0.20, "performance": 0.30, "scalability": 0.26},
    "video": {"cost": 0.12, "security": 0.12, "reliability": 0.20, "performance": 0.30, "scalability": 0.26},
    "iot": {"cost": 0.14, "security": 0.18, "reliability": 0.26, "performance": 0.16, "scalability": 0.26},
    "e-commerce": {"cost": 0.18, "security": 0.14, "reliability": 0.22, "performance": 0.20, "scalability": 0.26},
    "ecommerce": {"cost": 0.18, "security": 0.14, "reliability": 0.22, "performance": 0.20, "scalability": 0.26},
    "social": {"cost": 0.16, "security": 0.14, "reliability": 0.20, "performance": 0.22, "scalability": 0.28},
    "ride-sharing": {"cost": 0.14, "security": 0.14, "reliability": 0.22, "performance": 0.24, "scalability": 0.26},
    "education": {"cost": 0.22, "security": 0.14, "reliability": 0.20, "performance": 0.20, "scalability": 0.24},
    "learning": {"cost": 0.22, "security": 0.14, "reliability": 0.20, "performance": 0.20, "scalability": 0.24},
}


def detect_weight_profile(application_type: str) -> str:
    lowered = (application_type or "").lower()
    for key in DOMAIN_WEIGHT_PROFILES:
        if key != "default" and key in lowered:
            return key
    return "default"


def resolve_weights(
    application_type: str = "",
    context: Optional[ScoringContext] = None,
    overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Resolve overall-fitness weights for a run.

    Starts from the domain profile, then applies small requirement-driven
    nudges (cost sensitivity, strict SLA, high availability, compliance),
    renormalizes, and finally honors explicit user overrides if provided.
    Returns ``{"weights": {...}, "profile": str, "source": "auto"|"custom"}``.
    """
    if overrides:
        total = sum(float(v) for v in overrides.values())
        if total <= 0:
            raise ValueError("Custom weights must sum to a positive value.")
        norm = {k: float(v) / total for k, v in overrides.items()}
        # Fill any missing core dimensions with 0 so callers always see 5 keys.
        for dim in CORE_DIMENSIONS:
            norm.setdefault(dim, 0.0)
        s = sum(norm[d] for d in CORE_DIMENSIONS)
        norm = {d: norm[d] / s for d in CORE_DIMENSIONS}
        return {"weights": norm, "profile": "custom", "source": "custom"}

    profile = detect_weight_profile(application_type or (context.application_type if context else ""))
    weights = dict(DOMAIN_WEIGHT_PROFILES[profile])
    ctx = context or ScoringContext(application_type=application_type)

    # Requirement-driven nudges (kept small so domain character dominates).
    def nudge(dim: str, delta: float) -> None:
        weights[dim] = max(0.05, weights[dim] + delta)

    if ctx.cost_sensitive or (ctx.max_monthly_cost is not None):
        nudge("cost", 0.06)
    if ctx.security_level == "high" or ctx.compliance:
        nudge("security", 0.05)
    if ctx.availability_target >= 99.95:
        nudge("reliability", 0.04)
    if ctx.latency_sla_ms <= 100:
        nudge("performance", 0.05)
    if ctx.expected_users >= 100_000 or (ctx.scalability_type == "horizontal"):
        nudge("scalability", 0.04)

    total = sum(weights.values())
    weights = {k: round(v / total, 4) for k, v in weights.items()}
    # Fix rounding drift.
    drift = round(1.0 - sum(weights.values()), 4)
    if drift:
        top = max(weights, key=lambda k: weights[k])
        weights[top] = round(weights[top] + drift, 4)
    return {"weights": weights, "profile": profile, "source": "auto"}


# ---------------------------------------------------------------------------
# Dimension registry (extensibility point for future parameters)
# ---------------------------------------------------------------------------
# To add a new quality parameter (e.g. maintainability, observability):
#   1. Create ``evaluation/<name>_evaluator.py`` exposing
#      ``class <Name>Evaluator: evaluate(arch, context=None) -> EvaluatorResult``
#      where the result carries ``.score``, ``.breakdown`` and ``.grade``.
#   2. Register it here:  DIMENSION_REGISTRY["maintainability"] = "<module>:<class>".
#   3. Add its default weight to DOMAIN_WEIGHT_PROFILES (renormalize rows).
# The fitness engine, agents, API and UI read this registry / the weights dict,
# so no other code changes are required.

DIMENSION_REGISTRY: Dict[str, str] = {
    "cost": "evaluation.cost_evaluator:CostEvaluator",
    "security": "evaluation.security_evaluator:SecurityEvaluator",
    "reliability": "evaluation.reliability_evaluator:ReliabilityEvaluator",
    "performance": "evaluation.performance_evaluator:PerformanceEvaluator",
    "scalability": "evaluation.scalability_evaluator:ScalabilityEvaluator",
}
