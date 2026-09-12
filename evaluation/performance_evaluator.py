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


class PerformanceEvaluator:
    """Evaluates the performance characteristics of an architecture.

    Scores range from 0-100 where higher is better performance.
    """

    def evaluate(self, architecture: Architecture) -> EvaluatorResult:
        """Evaluate performance of an architecture based on its properties."""
        components = architecture.components
        communication_pattern = architecture.communication_pattern

        # Analyze performance-related features
        num_services = len(components)
        has_cache = any(c.type == "cache" for c in components)
        has_messaging = any(c.type == "messaging" for c in components)
        is_monolithic = num_services <= 2
        has_gateway = any(c.type == "gateway" for c in components)

        # Base score
        score = 50

        # Cache significantly improves performance
        if has_cache:
            score += 25

        # Gateway can help with routing and optimization
        if has_gateway:
            score += 5

        # Communication pattern matters
        if communication_pattern == "async":
            score += 5  # async can improve throughput
        elif communication_pattern == "sync":
            score -= 3  # sync can be bottleneck
        # event-driven is neutral

        # Many services can introduce latency
        if not is_monolithic and num_services > 5:
            score -= 10  # communication overhead
        elif not is_monolithic:
            score += 2  # parallelism benefit

        # Cap at 100
        score = max(0, min(100, score))

        # Build reasoning
        reasons_list = []
        if has_cache:
            reasons_list.append(
                "Cache present, reducing latency for repeated requests."
            )

        if communication_pattern == "async":
            reasons_list.append(
                "Asynchronous communication improves throughput."
            )
        elif communication_pattern == "sync":
            reasons_list.append(
                "Synchronous communication used."
            )

        if has_gateway:
            reasons_list.append(
                "API gateway enables request routing and optimization."
            )

        if is_monolithic:
            reasons_list.append(
                "Monolithic deployment reduces inter-service latency."
            )
        else:
            reasons_list.append(
                "Distributed services with potential communication overhead."
            )

        if not has_cache and not is_monolithic:
            reasons_list.append(
                "No cache; performance depends on database latency."
            )

        reasoning = " | ".join(reasons_list) if reasons_list else "Performance assessment based on caching and communication pattern."

        return EvaluatorResult(score=score, reasoning=reasoning)