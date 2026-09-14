from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .base import BaseAgent, AgentTraceEntry, LLMClient
from ..fitness.fitness_engine import Candidate


class CandidateDecision:
    """Explicit decision record explaining why a candidate was selected or rejected."""

    def __init__(
        self,
        architecture_name: str,
        fitness: float,
        selected: bool,
        reason: str,
        rank: int,
        strengths: List[str],
        weaknesses: List[str],
    ):
        self.architecture_name = architecture_name
        self.fitness = fitness
        self.selected = selected
        self.reason = reason
        self.rank = rank
        self.strengths = strengths
        self.weaknesses = weaknesses

    def to_dict(self) -> Dict[str, Any]:
        return {
            "architecture_name": self.architecture_name,
            "fitness": round(self.fitness, 2),
            "selected": self.selected,
            "outcome": "selected" if self.selected else "rejected",
            "reason": self.reason,
            "rank": self.rank,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
        }


class SelectionAgentResult:
    """Standardized selection result."""

    def __init__(
        self,
        selected: List[Candidate],
        rejected: List[Candidate],
        decisions: List[CandidateDecision],
    ):
        self.selected = selected
        self.rejected = rejected
        self.decisions = decisions


class SelectionAgent(BaseAgent):
    """Agent responsible for comparing candidates and selecting the strongest architectures for evolution.

    Defined Input:
        - candidates: List of evaluated Candidate objects.
        - selection_count: Number of top candidate architectures to preserve for mutation.

    Defined Output:
        - SelectionAgentResult containing selected and rejected candidates, with explicit reasons
          for every candidate's selection or rejection.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(
            name="Selection Agent",
            role="Ranks candidates by multi-objective fitness and selects strongest for evolutionary mutation with documented rationale",
            llm_client=llm_client,
        )

    def run(
        self,
        candidates: List[Candidate],
        selection_count: int = 2,
        generation: int = 0,
    ) -> Tuple[SelectionAgentResult, List[AgentTraceEntry]]:
        """Rank and select candidates, logging clear select/reject rationales."""
        if not candidates:
            return SelectionAgentResult([], [], []), []

        # Sort descending by overall fitness
        ranked = sorted(candidates, key=lambda c: c.overall_fitness, reverse=True)
        count = min(selection_count, len(ranked))

        selected_candidates = ranked[:count]
        rejected_candidates = ranked[count:]

        decisions: List[CandidateDecision] = []
        traces: List[AgentTraceEntry] = []

        for rank, cand in enumerate(ranked, 1):
            is_selected = rank <= count
            cand.selected_for_mutation = is_selected

            # Extract weaknesses and strengths if available
            strengths_list = []
            weaknesses_list = []
            if hasattr(cand, "evaluator_results") and isinstance(cand.evaluator_results, dict):
                for dim, res in cand.evaluator_results.items():
                    if hasattr(res, "strengths"):
                        strengths_list.extend(res.strengths)
                    if hasattr(res, "weaknesses"):
                        weaknesses_list.extend(res.weaknesses)

            if is_selected:
                reason = (
                    f"Selected (Rank #{rank}): High overall fitness ({cand.overall_fitness:.1f}/100) "
                    f"with strong performance in {[d for d in ['cost','security','reliability','performance','scalability'] if getattr(cand, d, 0) >= 75]}."
                )
                outcome = "selected"
            else:
                lowest_obj = min(["cost", "security", "reliability", "performance", "scalability"], key=lambda k: getattr(cand, k, 100))
                lowest_val = getattr(cand, lowest_obj, 0)
                reason = (
                    f"Rejected (Rank #{rank}): Fitness ({cand.overall_fitness:.1f}/100) below selection threshold "
                    f"(cutoff #{count} was {selected_candidates[-1].overall_fitness:.1f}); limited by {lowest_obj} ({lowest_val:.1f})."
                )
                outcome = "rejected"

            decision = CandidateDecision(
                architecture_name=cand.architecture.name,
                fitness=cand.overall_fitness,
                selected=is_selected,
                reason=reason,
                rank=rank,
                strengths=strengths_list,
                weaknesses=weaknesses_list,
            )
            decisions.append(decision)

            trace = AgentTraceEntry(
                agent=self.name,
                action="Select Candidate" if is_selected else "Reject Candidate",
                architecture=cand.architecture.name,
                reason=reason,
                outcome=outcome,
                fitness=cand.overall_fitness,
                generation=generation,
                details={
                    "rank": rank,
                    "selected": is_selected,
                    "scores": {
                        "cost": cand.cost,
                        "security": cand.security,
                        "reliability": cand.reliability,
                        "performance": cand.performance,
                        "scalability": cand.scalability,
                    },
                },
            )
            traces.append(trace)

        result = SelectionAgentResult(
            selected=selected_candidates,
            rejected=rejected_candidates,
            decisions=decisions,
        )
        return result, traces
