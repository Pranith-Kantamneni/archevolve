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


class SecurityEvaluator:
    """Evaluates the security posture of an architecture.

    Scores range from 0-100 where higher is more secure.
    """

    def evaluate(self, architecture: Architecture) -> EvaluatorResult:
        """Evaluate security of an architecture based on its properties."""
        components = architecture.components

        has_auth = any(
            "auth" in c.name.lower() or c.type == "gateway" or "vault" in c.name.lower() or c.type == "security"
            for c in components
        )
        num_gateways = sum(1 for c in components if c.type == "gateway")
        has_security_layer = any(c.type == "security" for c in components)
        num_services = len(components)
        is_monolithic = num_services <= 2

        score = 50  # base score

        if has_auth:
            score += 20
        if num_gateways > 0:
            score += 15
        else:
            score -= 5
        if has_security_layer:
            score += 10
        if is_monolithic:
            score += 5
        else:
            score += 2

        score = max(0, min(100, score))

        strengths = []
        weaknesses = []
        reasons_list = []

        if num_gateways > 0:
            strengths.append("API gateway provides edge security controls, rate limiting, and request filtering.")
            reasons_list.append("API gateway provides security controls and request filtering.")
        else:
            weaknesses.append("Missing API gateway exposes backend services directly to external traffic.")
            reasons_list.append("No API gateway, expanded attack surface.")

        if has_security_layer:
            strengths.append("Dedicated security component (secrets/encryption vault) safeguards sensitive credentials.")
            reasons_list.append("Dedicated security layer present.")

        if has_auth:
            strengths.append("Authentication/authorization enforcement present.")
            reasons_list.append("Authentication mechanism present.")
        else:
            weaknesses.append("No explicit authentication or identity gateway component found.")
            reasons_list.append("No explicit authentication component.")

        if is_monolithic:
            reasons_list.append("Monolithic architecture has smaller attack surface.")
        else:
            reasons_list.append("Microservices architecture with defense-in-depth possible.")

        if not strengths:
            strengths.append("Standard perimeter isolation.")
        if not weaknesses and score < 75:
            weaknesses.append("Lacks advanced threat prevention and dedicated secrets management.")

        reason = " | ".join(reasons_list)

        return EvaluatorResult(
            score=score,
            reasoning=reason,
            strengths=strengths,
            weaknesses=weaknesses,
            reason=reason,
        )