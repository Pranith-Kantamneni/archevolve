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
        self.reasoning = self.reason
        self.strengths = list(strengths or [])
        self.weaknesses = list(weaknesses or [])

    def __str__(self) -> str:
        return f"Score: {self.score:.1f} - {self.reason}"


class ScalabilityEvaluator:
    """Evaluates the scalability of an architecture.

    Scores range from 0-100 where higher is more scalable.
    """

    def evaluate(self, architecture: Architecture) -> EvaluatorResult:
        """Evaluate scalability of an architecture based on its properties."""
        components = architecture.components
        communication_pattern = architecture.communication_pattern
        deployment_strategy = architecture.deployment_strategy

        num_services = len(components)
        has_cache = any(c.type == "cache" for c in components)
        has_messaging = any(c.type == "messaging" for c in components)
        is_monolithic = num_services <= 2
        managed_count = sum(1 for c in components if c.managed)

        score = 50

        if not is_monolithic:
            score += 20
        else:
            score -= 10

        if has_messaging:
            score += 15

        if has_cache:
            score += 10

        if managed_count > 0:
            score += 5

        if is_monolithic:
            score -= 15

        score = max(0, min(100, score))

        strengths = []
        weaknesses = []
        reasons_list = []

        if not is_monolithic:
            strengths.append("Modular microservices layout enables independent auto-scaling per service tier.")
            reasons_list.append("Modular architecture enables horizontal scaling.")
        else:
            weaknesses.append("Monolithic deployment restricts horizontal elasticity and creates scaling bottlenecks.")
            reasons_list.append("Monolithic architecture limits horizontal scaling.")

        if has_messaging:
            strengths.append("Distributed message queue facilitates elastic event-driven worker scaling.")
            reasons_list.append("Messaging infrastructure supports event-driven scaling.")
        else:
            weaknesses.append("Synchronous request fan-out limits maximum concurrency under traffic surges.")

        if has_cache:
            strengths.append("Distributed cache layer offloads query volume, boosting concurrent read capacity.")
            reasons_list.append("Cache supports read scalability.")

        if managed_count > 0:
            reasons_list.append("Managed cloud services provide automated elasticity.")

        if not strengths:
            strengths.append("Baseline capacity for single-node scaling.")
        if not weaknesses and score < 75:
            weaknesses.append("Lacks auto-sharded database tier for petabyte-scale horizontal growth.")

        reason = " | ".join(reasons_list) if reasons_list else "Scalability assessment based on architecture type and infrastructure."

        return EvaluatorResult(
            score=score,
            reasoning=reason,
            strengths=strengths,
            weaknesses=weaknesses,
            reason=reason,
        )