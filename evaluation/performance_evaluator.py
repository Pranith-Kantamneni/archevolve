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


class PerformanceEvaluator:
    """Evaluates the performance characteristics of an architecture.

    Scores range from 0-100 where higher is better performance.
    """

    def evaluate(self, architecture: Architecture) -> EvaluatorResult:
        """Evaluate performance of an architecture based on its properties."""
        components = architecture.components
        communication_pattern = architecture.communication_pattern

        num_services = len(components)
        has_cache = any(c.type == "cache" for c in components)
        has_messaging = any(c.type == "messaging" for c in components)
        is_monolithic = num_services <= 2
        has_gateway = any(c.type == "gateway" for c in components)

        score = 50

        if has_cache:
            score += 25
        if has_gateway:
            score += 5

        if communication_pattern == "async":
            score += 5
        elif communication_pattern == "sync":
            score -= 3

        if not is_monolithic and num_services > 5:
            score -= 10
        elif not is_monolithic:
            score += 2

        score = max(0, min(100, score))

        strengths = []
        weaknesses = []
        reasons_list = []

        if has_cache:
            strengths.append("In-memory cache delivers sub-millisecond retrieval latency for hot data paths.")
            reasons_list.append("Cache present, reducing latency for repeated requests.")
        else:
            weaknesses.append("Absence of caching forces repeated disk I/O / database queries.")
            reasons_list.append("No cache; performance depends on database latency.")

        if communication_pattern == "async":
            strengths.append("Asynchronous pipeline unblocks request execution and maximizes throughput.")
            reasons_list.append("Asynchronous communication improves throughput.")
        elif communication_pattern == "sync":
            weaknesses.append("Synchronous request-response chaining introduces cascade latency.")
            reasons_list.append("Synchronous communication used.")

        if has_gateway:
            strengths.append("API gateway accelerates routing, SSL termination, and payload compression.")
            reasons_list.append("API gateway enables request routing and optimization.")

        if is_monolithic:
            reasons_list.append("Monolithic deployment reduces inter-service latency.")
        else:
            reasons_list.append("Distributed services with potential communication overhead.")

        if not strengths:
            strengths.append("Standard execution pipeline latency.")
        if not weaknesses and score < 75:
            weaknesses.append("Network serialization across microservices creates modest latency overhead.")

        reason = " | ".join(reasons_list) if reasons_list else "Performance assessment based on caching and communication pattern."

        return EvaluatorResult(
            score=score,
            reasoning=reason,
            strengths=strengths,
            weaknesses=weaknesses,
            reason=reason,
        )