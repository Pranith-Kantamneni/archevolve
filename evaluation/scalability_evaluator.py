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


class ScalabilityEvaluator:
    """Evaluates the scalability of an architecture.

    Scores range from 0-100 where higher is more scalable.
    """

    def evaluate(self, architecture: Architecture) -> EvaluatorResult:
        """Evaluate scalability of an architecture based on its properties."""
        components = architecture.components
        communication_pattern = architecture.communication_pattern
        deployment_strategy = architecture.deployment_strategy

        # Analyze scalability-related features
        num_services = len(components)
        has_cache = any(c.type == "cache" for c in components)
        has_messaging = any(c.type == "messaging" for c in components)
        is_monolithic = num_services <= 2
        managed_count = sum(1 for c in components if c.managed)

        # Base score
        score = 50

        # Stateless/services architecture scales horizontally
        if not is_monolithic:
            score += 20
        else:
            score -= 10  # monoliths harder to scale horizontally

        # Messaging/event-driven enables scaling
        if has_messaging:
            score += 15

        # Caches help with read scalability
        if has_cache:
            score += 10

        # Managed services can scale automatically
        if managed_count > 0:
            score += 5

        # Monolith penalty
        if is_monolithic:
            score -= 15  # significant scaling limitations

        # Cap at 100
        score = max(0, min(100, score))

        # Build reasoning
        reasons_list = []
        if not is_monolithic:
            reasons_list.append(
                "Modular architecture enables horizontal scaling."
            )
        else:
            reasons_list.append(
                "Monolithic architecture limits horizontal scaling."
            )

        if has_messaging:
            reasons_list.append(
                "Messaging infrastructure supports event-driven scaling."
            )

        if has_cache:
            reasons_list.append(
                "Cache supports read scalability."
            )

        if is_monolithic and not has_messaging and not has_cache:
            reasons_list.append(
                "Limited scalability features for horizontal growth."
            )

        reasoning = " | ".join(reasons_list) if reasons_list else "Scalability assessment based on architecture type and infrastructure."

        return EvaluatorResult(score=score, reasoning=reasoning)