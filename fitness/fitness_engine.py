from __future__ import annotations

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ..evaluation import FitnessResult, evaluate_architecture


@dataclass
class Candidate:
    """A candidate architecture with its evaluation scores."""
    architecture: object
    cost: float = 0.0
    security: float = 0.0
    reliability: float = 0.0
    performance: float = 0.0
    scalability: float = 0.0
    overall_fitness: float = 0.0
    generation: int = 0

    # Human-readable fields
    cost_reasoning: str = ""
    security_reasoning: str = ""
    reliability_reasoning: str = ""
    performance_reasoning: str = ""
    scalability_reasoning: str = ""

    # Metadata
    selected_for_mutation: bool = False
    mutation_source: str = ""  # which architecture this came from

    def compute_fitness(self) -> None:
        """Calculate overall fitness from objective scores using default equal weights."""
        self.overall_fitness = (
            0.20 * self.cost
            + 0.20 * self.security
            + 0.20 * self.reliability
            + 0.20 * self.performance
            + 0.20 * self.scalability
        )

    def __str__(self) -> str:
        return (
            f"Candidate [gen-{self.generation}] fitness={self.overall_fitness:.1f}\n"
            f"  Cost: {self.cost:.1f} ({self.cost_reasoning})\n"
            f"  Security: {self.security:.1f} ({self.security_reasoning})\n"
            f"  Reliability: {self.reliability:.1f} ({self.reliability_reasoning})\n"
            f"  Performance: {self.performance:.1f} ({self.performance_reasoning})\n"
            f"  Scalability: {self.scalability:.1f} ({self.scalability_reasoning})"
        )


class FitnessEngine:
    """Multi-objective fitness calculation engine."""

    # Default weights
    DEFAULT_WEIGHTS = {
        "cost": 0.20,
        "security": 0.20,
        "reliability": 0.20,
        "performance": 0.20,
        "scalability": 0.20,
    }

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
    ):
        """Initialize fitness engine.

        Args:
            weights: Dict mapping objective names to weights.
                     Must sum to 1.0. If None, uses defaults.
        """
        if weights is not None:
            total = sum(weights.values())
            if abs(total - 1.0) > 0.001:
                raise ValueError(f"Fitness weights must sum to 1.0, got {total}")
            self.weights = weights
        else:
            self.weights = self.DEFAULT_WEIGHTS

    def evaluate_and_score(
        self, architecture: object, generation: int = 0
    ) -> Candidate:
        """Evaluate an architecture and compute fitness scores.

        Args:
            architecture: Architecture model instance or dict
            generation: Current generation number

        Returns:
            Candidate with all scores populated
        """
        # Run the evaluation
        fitness_result = evaluate_architecture(architecture)

        # Create candidate with scores from evaluation
        candidate = Candidate(
            architecture=architecture,
            cost=fitness_result.cost,
            security=fitness_result.security,
            reliability=fitness_result.reliability,
            performance=fitness_result.performance,
            scalability=fitness_result.scalability,
            overall_fitness=fitness_result.overall,
            generation=generation,
            cost_reasoning=fitness_result.cost_reasoning,
            security_reasoning=fitness_result.security_reasoning,
            reliability_reasoning=fitness_result.reliability_reasoning,
            performance_reasoning=fitness_result.performance_reasoning,
            scalability_reasoning=fitness_result.scalability_reasoning,
        )

        # Compute fitness using configured weights
        if self.weights is not None:
            candidate.overall_fitness = (
                self.weights.get("cost", 0.20) * candidate.cost
                + self.weights.get("security", 0.20) * candidate.security
                + self.weights.get("reliability", 0.20) * candidate.reliability
                + self.weights.get("performance", 0.20) * candidate.performance
                + self.weights.get("scalability", 0.20) * candidate.scalability
            )
        else:
            candidate.compute_fitness()

        return candidate

    def rank_candidates(
        self, candidates: List[Candidate],
    ) -> List[Candidate]:
        """Rank candidates by overall fitness (descending)."""
        # Sort by overall_fitness descending
        ranked = sorted(
            candidates,
            key=lambda c: c.overall_fitness,
            reverse=True,
        )
        return ranked

    def select_top_candidates(
        self, candidates: List[Candidate],
        count: int = 2,
    ) -> List[Candidate]:
        """Select the top N candidates by fitness.

        Args:
            candidates: List of candidates to select from
            count: Number of top candidates to select

        Returns:
            Top 'count' candidates
        """
        ranked = self.rank_candidates(candidates)
        selected = ranked[:count]
        # Mark selected candidates
        for c in selected:
            c.selected_for_mutation = True
        return selected

    def configure_weights(
        self, weights: Dict[str, float],
    ) -> None:
        """Configure fitness weights.

        Weights must sum to 1.0.
        """
        total = sum(weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Fitness weights must sum to 1.0, got {total}")
        self.weights = weights