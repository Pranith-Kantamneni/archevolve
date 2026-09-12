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


class SecurityEvaluator:
    """Evaluates the security posture of an architecture.

    Scores range from 0-100 where higher is more secure.
    """

    def evaluate(self, architecture: Architecture) -> EvaluatorResult:
        """Evaluate security of an architecture based on its properties."""
        components = architecture.components

        # Check for security-related components and patterns
        has_auth = any(
            "auth" in c.name.lower() or c.type == "gateway" for c in components
        )
        num_gateways = sum(
            1 for c in components if c.type == "gateway"
        )
        num_services = len(components)
        is_monolithic = num_services <= 2

        # Scoring based on architectural security features
        score = 50  # base score

        # Authentication/gateway presence adds security
        if has_auth:
            score += 20

        # Gateway provides API security
        if num_gateways > 0:
            score += 15
        else:
            score -= 5

        # More services can mean larger attack surface, but also defense in depth
        if is_monolithic:
            score += 5  # attack surface is smaller
        else:
            score += 2  # defense in depth possible

        # Cap at 100
        score = max(0, min(100, score))

        # Build reasoning
        reasons_list = []
        if is_monolithic:
            reasons_list.append(
                "Monolithic architecture has smaller attack surface."
            )
        else:
            reasons_list.append(
                "Microservices architecture with defense-in-depth possible."
            )

        if num_gateways > 0:
            reasons_list.append("API gateway provides security controls and request filtering.")
        else:
            reasons_list.append("No API gateway, expanded attack surface.")

        if has_auth:
            reasons_list.append("Authentication mechanism present.")
        else:
            reasons_list.append("No explicit authentication component.")

        reasoning = " | ".join(reasons_list)

        return EvaluatorResult(score=score, reasoning=reasoning)