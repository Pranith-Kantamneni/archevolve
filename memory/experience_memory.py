from __future__ import annotations

import json
import os
from typing import List, Dict, Any, Optional


class ExperienceEntry:
    """A single structured experience entry stored in experience memory.

    Stores both SUCCESSFUL and FAILED architectural evolution experiences.
    """

    def __init__(
        self,
        architecture_name: str,
        generation: int = 0,
        objective_scores: Optional[Dict[str, float]] = None,
        fitness: float = 0.0,
        modifications: Optional[List[str]] = None,
        weaknesses: Optional[List[str]] = None,
        improvements: Optional[List[str]] = None,
        requirement_context: Any = None,
        outcome: str = "success",  # "success" | "failure"
        reason: str = "",
        changes_made: Optional[List[str]] = None,
        experience_used: Optional[Any] = None,
        application_type: str = "",
        requirements: str = "",
        architecture: Optional[str] = None,
    ):
        self.architecture_name = architecture_name or architecture or "unknown"
        self.architecture = architecture or self.architecture_name
        self.generation = int(generation)
        self.objective_scores = dict(objective_scores or {})
        self.evaluation_scores = self.objective_scores
        self.fitness = float(fitness)
        self.modifications = list(modifications or changes_made or [])
        self.changes_made = self.modifications
        self.weaknesses = list(weaknesses or [])
        self.improvements = list(improvements or [])
        self.requirement_context = requirement_context or {}
        self.outcome = str(outcome).lower()
        if self.outcome not in ("success", "failure"):
            self.outcome = "success" if self.fitness >= 70.0 else "failure"

        self.reason = reason or self._generate_default_reason()
        if isinstance(experience_used, list):
            self.experience_used = experience_used
        elif isinstance(experience_used, str) and experience_used:
            self.experience_used = [experience_used]
        else:
            self.experience_used = []

        self.application_type = application_type or (
            requirement_context.get("application_type", "")
            if isinstance(requirement_context, dict)
            else ""
        )
        self.requirements = requirements or (
            requirement_context.get("raw_input", "")
            if isinstance(requirement_context, dict)
            else str(requirement_context or "")
        )

    def _generate_default_reason(self) -> str:
        """Derive a descriptive reason from modifications and scores."""
        if self.outcome == "success":
            mods = ", ".join(self.modifications) if self.modifications else "Optimized components"
            return f"{mods} successfully achieved fitness {self.fitness:.1f}."
        else:
            weak = ", ".join(self.weaknesses) if self.weaknesses else "degraded trade-offs"
            return f"Architecture resulted in {weak} (fitness {self.fitness:.1f})."

    def to_dict(self) -> Dict[str, Any]:
        """Serialize entry to dictionary matching exact specification."""
        return {
            "architecture": self.architecture,
            "architecture_name": self.architecture_name,
            "application_type": self.application_type,
            "requirements": self.requirements,
            "generation": self.generation,
            "evaluation_scores": self.evaluation_scores,
            "objective_scores": self.objective_scores,
            "fitness": round(self.fitness, 2),
            "outcome": self.outcome,
            "reason": self.reason,
            "weaknesses": self.weaknesses,
            "changes_made": self.changes_made,
            "modifications": self.modifications,
            "improvements": self.improvements,
            "experience_used": self.experience_used,
            "requirement_context": self.requirement_context,
        }

    def __str__(self) -> str:
        prefix = "[SUCCESS]" if self.outcome == "success" else "[FAILURE]"
        return f"{prefix} {self.architecture_name} (Gen {self.generation}, Fitness {self.fitness:.1f}): {self.reason}"


class JsonExperienceMemory:
    """JSON-based experience memory for storing architectural patterns and feedback.

    Stores BOTH SUCCESSFUL and FAILED experiences.
    """

    def __init__(self, persistence_path: str = "experience_memory.json"):
        self.persistence_path = persistence_path
        self.entries: List[ExperienceEntry] = []

        if os.path.exists(self.persistence_path):
            self._load()

    def _load(self) -> None:
        """Load entries from JSON persistence file."""
        try:
            with open(self.persistence_path, "r") as f:
                data = json.load(f)
            self.entries = []
            for entry_data in data:
                entry = ExperienceEntry(
                    architecture_name=entry_data.get("architecture_name")
                    or entry_data.get("architecture", "unknown"),
                    architecture=entry_data.get("architecture"),
                    generation=entry_data.get("generation", 0),
                    objective_scores=entry_data.get(
                        "evaluation_scores", entry_data.get("objective_scores", {})
                    ),
                    fitness=entry_data.get("fitness", 0.0),
                    modifications=entry_data.get(
                        "changes_made", entry_data.get("modifications", [])
                    ),
                    changes_made=entry_data.get("changes_made"),
                    weaknesses=entry_data.get("weaknesses", []),
                    improvements=entry_data.get("improvements", []),
                    requirement_context=entry_data.get("requirement_context", {}),
                    outcome=entry_data.get("outcome", "success"),
                    reason=entry_data.get("reason", ""),
                    experience_used=entry_data.get("experience_used", []),
                    application_type=entry_data.get("application_type", ""),
                    requirements=entry_data.get("requirements", ""),
                )
                self.entries.append(entry)
        except (json.JSONDecodeError, IOError):
            self.entries = []

    def _save(self) -> None:
        """Save entries to JSON persistence file."""
        data = [entry.to_dict() for entry in self.entries]
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.persistence_path)), exist_ok=True)
        except Exception:
            pass
        with open(self.persistence_path, "w") as f:
            json.dump(data, f, indent=2)

    def add(
        self,
        architecture_name: str,
        generation: int,
        objective_scores: Dict[str, float],
        fitness: float,
        modifications: Optional[List[str]] = None,
        weaknesses: Optional[List[str]] = None,
        improvements: Optional[List[str]] = None,
        requirement_context: Any = None,
        outcome: Optional[str] = None,
        reason: Optional[str] = None,
        changes_made: Optional[List[str]] = None,
        experience_used: Optional[Any] = None,
        application_type: str = "",
        requirements: str = "",
        architecture: Optional[str] = None,
    ) -> ExperienceEntry:
        """Add a new experience entry (supports both successes and failures)."""
        if outcome is None:
            outcome = "success" if fitness >= 70.0 else "failure"

        entry = ExperienceEntry(
            architecture_name=architecture_name,
            generation=generation,
            objective_scores=objective_scores,
            fitness=fitness,
            modifications=modifications or changes_made or [],
            weaknesses=weaknesses or [],
            improvements=improvements or [],
            requirement_context=requirement_context or {},
            outcome=outcome,
            reason=reason or "",
            changes_made=changes_made or modifications or [],
            experience_used=experience_used,
            application_type=application_type,
            requirements=requirements,
            architecture=architecture or architecture_name,
        )
        self.entries.append(entry)
        self._save()
        return entry

    def get_successes(self, limit: int = 10) -> List[ExperienceEntry]:
        """Return successful experiences."""
        successes = [e for e in self.entries if e.outcome == "success"]
        successes.sort(key=lambda e: e.fitness, reverse=True)
        return successes[:limit]

    def get_failures(self, limit: int = 10) -> List[ExperienceEntry]:
        """Return failed experiences."""
        failures = [e for e in self.entries if e.outcome == "failure"]
        failures.sort(key=lambda e: e.generation, reverse=True)
        return failures[:limit]

    def recent_entries(
        self,
        limit: int = 5,
        min_score: Optional[float] = None,
        outcome: Optional[str] = None,
    ) -> List[ExperienceEntry]:
        """Get recent entries, optionally filtered by minimum fitness or outcome."""
        filtered = list(self.entries)
        if outcome is not None:
            filtered = [e for e in filtered if e.outcome.lower() == outcome.lower()]
        if min_score is not None:
            filtered = [e for e in filtered if e.fitness >= min_score]

        filtered.sort(key=lambda e: e.generation, reverse=True)
        return filtered[:limit]

    def entries_by_weakness(self, weakness_pattern: str) -> List[ExperienceEntry]:
        """Find entries that contained a specific weakness pattern."""
        return [
            e for e in self.entries
            if any(weakness_pattern.lower() in w.lower() for w in e.weaknesses)
        ]

    def best_entries(self, count: int = 3) -> List[ExperienceEntry]:
        """Get the best entries by fitness."""
        sorted_entries = sorted(self.entries, key=lambda e: e.fitness, reverse=True)
        return sorted_entries[:count]

    def get_relevant_experiences(
        self,
        application_type: Optional[str] = None,
        weaknesses: Optional[List[str]] = None,
        limit: int = 4,
    ) -> Dict[str, List[ExperienceEntry]]:
        """Retrieve relevant previous successes AND failures to inform mutations."""
        app_type_clean = (application_type or "").lower().strip()
        app_matches = [
            e for e in self.entries
            if app_type_clean and (app_type_clean in e.application_type.lower() or e.application_type.lower() in app_type_clean)
        ]

        pool = app_matches if app_matches else self.entries

        successes = [e for e in pool if e.outcome == "success"]
        failures = [e for e in pool if e.outcome == "failure"]

        successes.sort(key=lambda e: e.fitness, reverse=True)
        failures.sort(key=lambda e: e.generation, reverse=True)

        return {
            "successes": successes[:limit],
            "failures": failures[:limit],
        }

    def __str__(self) -> str:
        s_count = sum(1 for e in self.entries if e.outcome == "success")
        f_count = sum(1 for e in self.entries if e.outcome == "failure")
        return f"ExperienceMemory({len(self.entries)} entries: {s_count} successes, {f_count} failures)"