from __future__ import annotations

from typing import Tuple, Dict, Any

from ..models.architecture import Architecture, Component


class EvaluatorResult:
    """Result from an architecture evaluator."""

    def __init__(
        self,
        score: float,
        reasoning: str = "",
        strengths: list[str] | None = None,
        weaknesses: list[str] | None = None,
        reason: str | None = None,
    ):
        self.score = float(score)
        self.reason = reason if reason is not None else reasoning
        self.reasoning = self.reason  # backwards-compatibility alias
        self.strengths = list(strengths or [])
        self.weaknesses = list(weaknesses or [])

    def __str__(self) -> str:
        return f"Score: {self.score:.1f} - {self.reason}"


class CostEvaluator:
    """Evaluates the cost of an architecture.

    Scores range from 0-100 where higher is better (lower cost).
    """

    def evaluate(self, architecture: Architecture) -> EvaluatorResult:
        """Evaluate cost of an architecture based on its properties."""
        components = architecture.components

        # Count services and components
        num_services = len(components)
        num_databases = sum(1 for c in components if c.type == "database")
        num_caches = sum(1 for c in components if c.type == "cache")
        num_gateways = sum(1 for c in components if c.type == "gateway")
        num_messaging = sum(1 for c in components if c.type == "messaging")
        managed_count = sum(1 for c in components if c.managed)

        service_penalty = num_services * 3  # each service costs ~3 points
        managed_penalty = managed_count * 2  # managed services add cost
        database_penalty = num_databases * 5  # databases are expensive
        cache_penalty = num_caches * 2
        messaging_penalty = num_messaging * 2
        gateway_penalty = num_gateways * 1

        raw_score = 100 - service_penalty - managed_penalty - database_penalty - cache_penalty - messaging_penalty - gateway_penalty
        score = max(0, min(100, raw_score))

        strengths = []
        weaknesses = []
        reasons = []

        if num_services <= 3:
            strengths.append(f"Lean component count ({num_services} components) minimizes base hosting costs.")
        elif num_services > 5:
            weaknesses.append(f"High component count ({num_services} components) increases operational infrastructure cost.")

        if managed_count == 0:
            strengths.append("Self-hosted components eliminate cloud vendor managed service premiums.")
        else:
            reasons.append(f"Uses {managed_count} managed service(s) adding operational cost but reducing maintenance.")
            if managed_count > 3:
                weaknesses.append(f"Heavy reliance on {managed_count} managed services increases monthly cloud billing.")

        if num_databases > 1:
            weaknesses.append(f"Multiple database instances ({num_databases}) significantly contribute to provisioned cost.")
        elif num_databases == 1:
            strengths.append("Single database instance optimizes baseline storage footprint.")

        if not strengths:
            strengths.append("Moderate resource footprint suitable for standard workloads.")
        if not weaknesses and score < 75:
            weaknesses.append("Component composition imposes moderate monthly cloud infrastructure costs.")

        if reasons:
            reason = " | ".join(reasons)
        elif weaknesses:
            reason = f"Cost efficiency score {score:.1f}/100: " + "; ".join(weaknesses[:2])
        else:
            reason = f"Cost efficiency score {score:.1f}/100: " + "; ".join(strengths[:2])

        return EvaluatorResult(
            score=score,
            reasoning=reason,
            strengths=strengths,
            weaknesses=weaknesses,
            reason=reason,
        )