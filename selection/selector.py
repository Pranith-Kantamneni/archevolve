from __future__ import annotations

import random
from typing import List, Dict, Any

from ..fitness.fitness_engine import Candidate


class SelectionResult:
    """Result from a selection operation."""

    def __init__(
        self,
        selected: List[Candidate],
        rejected: List[Candidate],
        ranking: List[int],
    ):
        self.selected = selected
        self.rejected = rejected
        self.ranking = ranking  # position -> candidate index mapping

    def __str__(self) -> str:
        lines = ["Selection Result:"]
        for i, c in enumerate(self.selected):
            lines.append(
                f"  {i + 1}. Fitness: {c.overall_fitness:.1f} - {c.architecture.name}"
            )
        return "\n".join(lines)


class Selector:
    """Fitness-based selection mechanism."""

    def select(
        self, candidates: List[Candidate], count: int
    ) -> SelectionResult:
        """Select top candidates by fitness.

        Args:
            candidates: List of candidates to select from
            count: Number of top candidates to select

        Returns:
            SelectionResult with selected and rejected candidates
        """
        if count <= 0:
            return SelectionResult(selected=[], rejected=[], ranking=[])

        if count >= len(candidates):
            # Select all
            for c in candidates:
                c.selected_for_mutation = True
            return SelectionResult(
                selected=candidates,
                rejected=[],
                ranking=list(range(len(candidates))),
            )

        # Rank candidates by fitness (descending)
        ranked = sorted(
            enumerate(candidates),
            key=lambda x: x[1].overall_fitness,
            reverse=True,
        )

        # Select top 'count'
        selected_indices = [idx for idx, _ in ranked[:count]]
        selected = [candidates[idx] for idx in selected_indices]
        rejected = [candidates[idx] for idx, _ in ranked[count:]]

        # Mark selected candidates
        for c in selected:
            c.selected_for_mutation = True

        # Build ranking map: original position -> rank position
        ranking = {}
        for rank, (orig_idx, _) in enumerate(ranked):
            ranking[orig_idx] = rank

        return SelectionResult(
            selected=selected,
            rejected=rejected,
            ranking=sorted(ranking.values()),
        )

    def tournament_selection(
        self, candidates: List[Candidate], count: int, tournament_size: int = 3
    ) -> List[Candidate]:
        """Select candidates using tournament selection.

        Args:
            candidates: List of candidates to select from
            count: Number of candidates to select
            tournament_size: Number of candidates per tournament

        Returns:
            List of selected candidates
        """
        selected = []
        pool = list(candidates)

        while len(selected) < count and pool:
            # Randomly select tournament participants
            participants = random.sample(
                pool, min(tournament_size, len(pool))
            )

            # Pick the best from participants
            winner = max(participants, key=lambda c: c.overall_fitness)
            selected.append(winner)

            # Remove winner from pool
            pool = [c for c in pool if c is not winner]

        return selected