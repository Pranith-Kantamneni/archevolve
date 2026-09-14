from __future__ import annotations

import hashlib
import json
from typing import List, Dict, Any, Optional

from ..requirements import parse_requirement
from ..requirements.constraints import apply_constraints_to_parsed
from ..generation.architecture_generator import ArchitectureGenerator
from ..evaluation import evaluate_architecture
from ..fitness.fitness_engine import FitnessEngine, Candidate
from ..selection.selector import Selector
from ..mutation.mutation_engine import MutationEngine
from ..memory.experience_memory import JsonExperienceMemory
from ..models.graph import derive_connections
from ..agents.orchestrator import MultiAgentOrchestrator, _stable_seed


class EvolutionEngine:
    """Evolutionary engine for architecture design powered by specialized multi-agent architecture.

    Orchestrates the specialized multi-agent workflow:
    - Requirement Analysis Agent
    - Architecture Generation Agent
    - Evaluation Agents (Cost, Security, Reliability, Performance, Scalability)
    - Selection Agent
    - Experience Memory Agent (Dual Success & Failure tracking)
    - Architecture Evolution / Mutation Agent
    - Final Architecture Agent

    Deterministic by default: no external API keys required.
    """

    def __init__(
        self,
        population_size: int = 5,
        max_generations: int = 5,
        selection_count: int = 2,
        mutation_count: int = 2,
        weights: Optional[Dict[str, float]] = None,
        use_llm: bool = False,
        experience_path: str = "experience_memory.json",
        stopping_threshold: Optional[float] = None,
        stagnation_limit: int = 2,
        application_type: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
    ):
        self.population_size = population_size
        self.max_generations = max_generations
        self.selection_count = selection_count
        self.mutation_count = mutation_count
        self.use_llm = use_llm
        self.stagnation_limit = stagnation_limit
        self.application_type = application_type or ""
        self.constraints = constraints or {}
        self.experience_path = experience_path
        self.weights = weights
        self.stopping_threshold = stopping_threshold

        seed_text = json.dumps(
            {"app": self.application_type or "", "constraints": self.constraints},
            sort_keys=True,
        )
        self.seed = seed if seed is not None else _stable_seed(seed_text)

        # Backwards compatible component references
        self.fitness_engine = FitnessEngine(weights=weights)
        self.selector = Selector()
        self.mutation_engine = MutationEngine(
            use_llm=use_llm, mutation_count=mutation_count, seed=self.seed
        )
        self.experience_memory = JsonExperienceMemory(experience_path)

        # Multi-agent orchestrator instance
        self.orchestrator = MultiAgentOrchestrator(
            population_size=population_size,
            max_generations=max_generations,
            selection_count=selection_count,
            mutation_count=mutation_count,
            weights=weights,
            use_llm=use_llm,
            experience_path=experience_path,
            stopping_threshold=stopping_threshold,
            stagnation_limit=stagnation_limit,
            application_type=self.application_type,
            constraints=self.constraints,
            seed=self.seed,
        )

        # Expose orchestrator memory to engine
        self.experience_memory = self.orchestrator.memory_agent.memory

        # Tracking state
        self.generation = 0
        self.evaluation_history: List[float] = []
        self.population_history: List[List[Candidate]] = []
        self.generation_history: List[Dict[str, Any]] = []
        self.candidates_evaluated = 0
        self.experience_used: List[str] = []
        self.best_candidate = None

    def run(self, raw_requirement: str) -> Dict[str, Any]:
        """Run the complete multi-agent evolutionary pipeline."""
        self._log(f"1. REQUIREMENT ANALYSIS AGENT: {raw_requirement}")
        results = self.orchestrator.run(raw_requirement)

        # Sync engine state for backwards compatibility
        self.generation_history = self.orchestrator.generation_history
        self.experience_used = self.orchestrator.experience_used
        self.generation = results.get("evolution_history", {}).get("generations_run", 0)
        self.candidates_evaluated = results.get("evolution_history", {}).get("candidates_evaluated", 0)

        # Log trace summary
        for trace in self.orchestrator.agent_trace:
            self._log(f"   [{trace.agent}] {trace.action}: {trace.reason}")

        return results

    def _log(self, message: str) -> None:
        """Log execution progress."""
        print(message)