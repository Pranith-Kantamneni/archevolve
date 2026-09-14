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


class ReliabilityEvaluator:
    """Evaluates the reliability of an architecture.

    Scores range from 0-100 where higher is more reliable.
    """

    def evaluate(self, architecture: Architecture) -> EvaluatorResult:
        """Evaluate reliability of an architecture based on its properties."""
        components = architecture.components

        num_services = len(components)
        has_cache = any(c.type == "cache" for c in components)
        has_messaging = any(c.type == "messaging" for c in components)
        num_instances = sum(c.quantity for c in components)
        has_db_managed = any(c.type == "database" and c.managed for c in components)
        has_replication = any(c.quantity > 1 for c in components)

        score = 50

        if num_instances >= 3:
            score += 20
        elif num_instances >= 2:
            score += 10

        if has_cache:
            score += 10

        if has_messaging:
            score += 10

        if has_db_managed:
            score += 10

        if num_services <= 2 and not has_cache:
            score -= 5

        score = max(0, min(100, score))

        strengths = []
        weaknesses = []
        reasons_list = []

        if num_instances >= 3 or has_replication:
            strengths.append(f"Multi-instance redundancy ({num_instances} active nodes) mitigates single points of failure.")
            reasons_list.append(f"{num_instances} instances provide redundancy.")
        else:
            weaknesses.append("Single-instance deployment risks service outage upon node failure.")

        if has_cache:
            strengths.append("In-memory caching cushions backend datastores against traffic surges.")
            reasons_list.append("Cache reduces database load, improving reliability.")

        if has_messaging:
            strengths.append("Asynchronous message buffering enables graceful degradation during peak loads.")
            reasons_list.append("Messaging decouples services, improving fault tolerance.")
        else:
            weaknesses.append("Direct synchronous inter-service coupling lacks backpressure buffering.")

        if has_db_managed:
            strengths.append("Managed datastore provides automated failover, backups, and point-in-time recovery.")
            reasons_list.append("Managed database includes reliability features.")

        if num_services <= 2 and not has_cache:
            weaknesses.append("Monolithic coupling creates broad failure blast radius.")

        if not strengths:
            strengths.append("Baseline availability suitable for non-critical workloads.")
        if not weaknesses and score < 75:
            weaknesses.append("Lacks multi-region replication and automated circuit breaking.")

        reason = " | ".join(reasons_list) if reasons_list else "Reliability based on component redundancy and features."

        return EvaluatorResult(
            score=score,
            reasoning=reason,
            strengths=strengths,
            weaknesses=weaknesses,
            reason=reason,
        )