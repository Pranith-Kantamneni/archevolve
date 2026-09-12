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


class ReliabilityEvaluator:
    """Evaluates the reliability of an architecture.

    Scores range from 0-100 where higher is more reliable.
    """

    def evaluate(self, architecture: Architecture) -> EvaluatorResult:
        """Evaluate reliability of an architecture based on its properties."""
        components = architecture.components

        # Analyze reliability-related features
        num_services = len(components)
        has_cache = any(c.type == "cache" for c in components)
        has_messaging = any(c.type == "messaging" for c in components)
        num_instances = sum(c.quantity for c in components)
        has_db_managed = any(c.type == "database" and c.managed for c in components)

        # Base score
        score = 50

        # Redundancy through multiple instances
        if num_instances >= 3:
            score += 20
        elif num_instances >= 2:
            score += 10

        # Cache improves reliability by reducing database load
        if has_cache:
            score += 10

        # Messaging improves reliability through decoupling
        if has_messaging:
            score += 10

        # Managed databases often have better reliability features
        if has_db_managed:
            score += 10

        # Monoliths have single point of failure risk
        if num_services <= 2 and not has_cache:
            score -= 5

        # Cap at 100
        score = max(0, min(100, score))

        # Build reasoning
        reasons_list = []
        if num_instances >= 3:
            reasons_list.append(
                f"{num_instances} instances provide redundancy."
            )
        elif num_instances >= 2:
            reasons_list.append(
                f"{num_instances} instance provides some redundancy."
            )

        if has_cache:
            reasons_list.append(
                "Cache reduces database load, improving reliability."
            )

        if has_messaging:
            reasons_list.append(
                "Messaging decouples services, improving fault tolerance."
            )

        if has_db_managed:
            reasons_list.append(
                "Managed database includes reliability features."
            )

        reasoning = " | ".join(reasons_list) if reasons_list else "Reliability based on component redundancy and features."

        return EvaluatorResult(score=score, reasoning=reasoning)