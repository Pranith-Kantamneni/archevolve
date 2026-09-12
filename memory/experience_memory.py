from __future__ import annotations

import json
import os
from typing import List, Dict, Any, Optional

from ..mutation.mutation_engine import ExperienceEntry


class JsonExperienceMemory:
    """JSON-based experience memory for storing architectural patterns and feedback.

    Stores:
    - architecture
    - generation
    - objective scores
    - fitness
    - successful modifications
    - weaknesses
    - improvements
    - requirement context

    For MVP, JSON persistence is used. Can be swapped for SQLite later.
    """

    def __init__(self, persistence_path: str = "experience_memory.json"):
        """Initialize experience memory.

        Args:
            persistence_path: Path to JSON file for persistence
        """
        self.persistence_path = persistence_path
        self.entries: List[ExperienceEntry] = []

        # Load existing entries if file exists
        if os.path.exists(self.persistence_path):
            self._load()

    def _load(self) -> None:
        """Load entries from JSON persistence file."""
        try:
            with open(self.persistence_path, "r") as f:
                data = json.load(f)
            for entry_data in data:
                entry = ExperienceEntry(
                    architecture_name=entry_data.get("architecture_name", "unknown"),
                    generation=entry_data.get("generation", 0),
                    objective_scores=entry_data.get("objective_scores", {}),
                    fitness=entry_data.get("fitness", 0.0),
                    modifications=entry_data.get("modifications", []),
                    weaknesses=entry_data.get("weaknesses", []),
                    improvements=entry_data.get("improvements", []),
                    requirement_context=entry_data.get("requirement_context", {}),
                )
                self.entries.append(entry)
        except (json.JSONDecodeError, IOError):
            # Start fresh if file is corrupted
            self.entries = []

    def _save(self) -> None:
        """Save entries to JSON persistence file."""
        data = []
        for entry in self.entries:
            data.append({
                "architecture_name": entry.architecture_name,
                "generation": entry.generation,
                "objective_scores": entry.objective_scores,
                "fitness": entry.fitness,
                "modifications": entry.modifications,
                "weaknesses": entry.weaknesses,
                "improvements": entry.improvements,
                "requirement_context": entry.requirement_context,
            })
        with open(self.persistence_path, "w") as f:
            json.dump(data, f, indent=2)

    def add(
        self,
        architecture_name: str,
        generation: int,
        objective_scores: Dict[str, float],
        fitness: float,
        modifications: List[str],
        weaknesses: List[str],
        improvements: List[str],
        requirement_context: Dict[str, Any],
    ) -> None:
        """Add a new experience entry.

        Args:
            architecture_name: Name of the architecture
            generation: Generation number
            objective_scores: Dict of objective -> score
            fitness: Overall fitness score
            modifications: List of modifications made
            weaknesses: List of identified weaknesses
            improvements: List of observed improvements
            requirement_context: Original requirement context
        """
        entry = ExperienceEntry(
            architecture_name=architecture_name,
            generation=generation,
            objective_scores=objective_scores,
            fitness=fitness,
            modifications=modifications,
            weaknesses=weaknesses,
            improvements=improvements,
            requirement_context=requirement_context,
        )
        self.entries.append(entry)
        self._save()

    def recent_entries(
        self,
        limit: int = 5,
        min_score: Optional[float] = None,
    ) -> List[ExperienceEntry]:
        """Get recent entries, optionally filtered by minimum fitness.

        Args:
            limit: Maximum number of entries to return
            min_score: Minimum fitness score to include

        Returns:
            List of ExperienceEntry objects
        """
        filtered = self.entries
        if min_score is not None:
            filtered = [e for e in filtered if e.fitness >= min_score]

        # Sort by generation descending (most recent first)
        filtered.sort(key=lambda e: e.generation, reverse=True)

        return filtered[:limit]

    def entries_by_weakness(self, weakness_pattern: str) -> List[ExperienceEntry]:
        """Find entries that contained a specific weakness pattern.

        Args:
            weakness_pattern: Substring to match against weaknesses

        Returns:
            List of matching ExperienceEntry objects
        """
        return [
            e for e in self.entries
            if any(weakness_pattern.lower() in w.lower() for w in e.weaknesses)
        ]

    def best_entries(self, count: int = 3) -> List[ExperienceEntry]:
        """Get the best entries by fitness.

        Args:
            count: Number of top entries to return

        Returns:
            List of top ExperienceEntry objects by fitness
        """
        sorted_entries = sorted(self.entries, key=lambda e: e.fitness, reverse=True)
        return sorted_entries[:count]

    def __str__(self) -> str:
        return f"ExperienceMemory({len(self.entries)} entries)"