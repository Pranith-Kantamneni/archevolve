from __future__ import annotations

from typing import Tuple, Dict, Any

from ..models.architecture import Architecture, Component


class EvaluatorResult:
    """Result from an architecture evaluator."""

    def __init__(
        self,
        score: float,
        reasoning: str,
    ):
        self.score = score
        self.reasoning = reasoning

    def __str__(self) -> str:
        return f"Score: {self.score:.1f} - {self.reasoning}"


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

        # Heuristic scoring based on architectural properties
        # More services generally mean higher cost
        # Managed services add operational cost but reduce engineering cost
        # Fewer components generally mean lower cost

        service_penalty = num_services * 3  # each service costs ~3 points
        managed_penalty = managed_count * 2  # managed services add cost
        database_penalty = num_databases * 5  # databases are expensive
        cache_penalty = num_caches * 2
        messaging_penalty = num_messaging * 2
        gateway_penalty = num_gateways * 1

        raw_score = 100 - service_penalty - managed_penalty - database_penalty - cache_penalty - messaging_penalty - gateway_penalty

        # Ensure score is bounded 0-100
        score = max(0, min(100, raw_score))

        # Build reasoning
        reasons = []
        if managed_count > 0:
            reasons.append(
                f"Uses {managed_count} managed service(s), which adds operational cost but reduces engineering overhead."
            )
        if num_databases > 0:
            reasons.append(
                f"Has {num_databases} database component(s), which contributes to infrastructure cost."
            )
        if num_services > 5:
            reasons.append(
                f"Many services ({num_services}) increase operational complexity and cost."
            )
        elif num_services <= 3:
            reasons.append(
                "Few services keep infrastructure cost moderate."
            )

        if not reasons:
            reasons.append(
                "Cost assessment based on component count and managed service usage."
            )

        reasoning = " | ".join(reasons)

        return EvaluatorResult(score=score, reasoning=reasoning)