from __future__ import annotations

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ..evaluation import FitnessResult, evaluate_architecture
from ..evaluation.scoring import CORE_DIMENSIONS, ScoringContext, grade_for, resolve_weights


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
    evaluator_results: Dict[str, Any] = field(default_factory=dict)

    # Production-grade scoring transparency (populated by FitnessEngine)
    breakdowns: Dict[str, Dict[str, float]] = field(default_factory=dict)
    grades: Dict[str, str] = field(default_factory=dict)
    weights_used: Dict[str, float] = field(default_factory=dict)
    weight_profile: str = "default"
    # Domain-specific parameter scores {name: score} + transparency
    extra_scores: Dict[str, float] = field(default_factory=dict)
    extra_grades: Dict[str, str] = field(default_factory=dict)
    extra_breakdowns: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def compute_fitness(self, weights: Optional[Dict[str, float]] = None) -> None:
        """Calculate overall fitness from objective scores using given (or equal) weights."""
        w = weights or {d: 0.20 for d in CORE_DIMENSIONS}
        self.overall_fitness = sum(w.get(d, 0.0) * getattr(self, d, 0.0) for d in CORE_DIMENSIONS)

    @property
    def overall_grade(self) -> str:
        return grade_for(self.overall_fitness)

    def __str__(self) -> str:
        return (
            f"Candidate [gen-{self.generation}] fitness={self.overall_fitness:.1f} ({self.overall_grade})\n"
            f"  Cost: {self.cost:.1f} ({self.cost_reasoning})\n"
            f"  Security: {self.security:.1f} ({self.security_reasoning})\n"
            f"  Reliability: {self.reliability:.1f} ({self.reliability_reasoning})\n"
            f"  Performance: {self.performance:.1f} ({self.performance_reasoning})\n"
            f"  Scalability: {self.scalability:.1f} ({self.scalability_reasoning})"
        )


class FitnessEngine:
    """Multi-objective fitness calculation engine.

    Weights are application-aware: when ``weights`` is None they are resolved
    per run from the application domain + requirements (see
    ``evaluation.scoring.resolve_weights``) instead of always using equal
    0.20 weights.
    """

    # Default weights (used only when no context is available)
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
                      Must sum to 1.0. If None, weights are resolved per
                      evaluation from the scoring context (application-aware).
        """
        if weights is not None:
            total = sum(weights.values())
            if abs(total - 1.0) > 0.001:
                raise ValueError(f"Fitness weights must sum to 1.0, got {total}")
            self.weights: Optional[Dict[str, float]] = dict(weights)
            self._auto_weights = False
        else:
            self.weights = None  # auto-resolve per evaluation
            self._auto_weights = True

    def _resolve(
        self,
        context: Any = None,
        application_type: str = "",
    ) -> Dict[str, Any]:
        if self.weights is not None:
            total = sum(self.weights.values())
            norm = {k: float(v) / total for k, v in self.weights.items()}
            for dim in CORE_DIMENSIONS:
                norm.setdefault(dim, 0.0)
            return {"weights": norm, "profile": "custom", "source": "custom"}
        ctx = context if isinstance(context, ScoringContext) else ScoringContext.from_any(context, application_type)
        return resolve_weights(ctx.application_type or application_type, ctx)

    def evaluate_and_score(
        self, architecture: object, generation: int = 0,
        context: Any = None, application_type: str = "",
    ) -> Candidate:
        """Evaluate an architecture and compute fitness scores.

        Args:
            architecture: Architecture model instance or dict
            generation: Current generation number
            context: ParsedRequirement / StructuredRequirements / dict used to
                condition scoring thresholds and resolve weights.
            application_type: Application domain (used for weight profiles).

        Returns:
            Candidate with all scores populated
        """
        resolved = self._resolve(context, application_type)
        w = resolved["weights"]
        fitness_result = evaluate_architecture(
            architecture, context=context, weights=w, application_type=application_type,
        )

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
            breakdowns=dict(fitness_result.breakdowns),
            grades=dict(fitness_result.grades),
            weights_used=dict(fitness_result.weights),
            weight_profile=fitness_result.weight_profile,
            extra_scores={k: float(v["score"]) for k, v in fitness_result.domain_params.items()},
            extra_grades={k: v["grade"] for k, v in fitness_result.domain_params.items()},
            extra_breakdowns={k: dict(v["breakdown"]) for k, v in fitness_result.domain_params.items()},
        )
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
        self.weights = dict(weights)
        self._auto_weights = False
