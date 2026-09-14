from __future__ import annotations

import hashlib
import json
import os
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


def _stable_seed(text: str) -> int:
    """Derive a deterministic seed from the input description."""
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


class EvolutionEngine:
    """Complete evolutionary engine for architecture design.

    Orchestrates the full generate-evaluate-evolve loop inspired by AlphaEvolve.
    Deterministic by default: the same input produces the same result, and
    different application types / requirements produce different results.
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

        seed_text = json.dumps(
            {"app": self.application_type or "", "constraints": self.constraints},
            sort_keys=True,
        )
        self.seed = seed if seed is not None else _stable_seed(seed_text)

        self.fitness_engine = FitnessEngine(weights=weights)
        self.selector = Selector()
        self.mutation_engine = MutationEngine(
            use_llm=use_llm, mutation_count=mutation_count, seed=self.seed
        )
        self.experience_memory = JsonExperienceMemory(experience_path)

        # Tracking state
        self.generation = 0
        self.evaluation_history: List[float] = []
        self.population_history: List[List[Candidate]] = []
        self.generation_history: List[Dict[str, Any]] = []
        self.candidates_evaluated = 0
        self.experience_used: List[str] = []
        self.stopping_threshold = stopping_threshold
        self.stagnation_counter = 0
        self.initial_population = None
        self.best_candidate = None

    def run(self, raw_requirement: str) -> Dict[str, Any]:
        """Run the complete evolutionary loop.

        Args:
            raw_requirement: Natural-language software requirement

        Returns:
            Dictionary with complete evolution results
        """
        parsed = parse_requirement(raw_requirement)
        parsed = apply_constraints_to_parsed(parsed, self.constraints)
        self._log(f"1. REQUIREMENTS: {raw_requirement}")
        self._log(f"2. PARSED REQUIREMENTS: {parsed.raw_input}")

        # Generate initial population (application-aware, deterministic per input)
        generator = ArchitectureGenerator(
            population_size=self.population_size,
            seed=self.seed,
            application_type=self.application_type,
            constraints=self.constraints,
        )
        raw_population = generator.generate_initial_population(
            raw_requirement,
            application_type=self.application_type,
            constraints=self.constraints,
        )
        self._log(f"3. INITIAL POPULATION: {len(raw_population)} candidates")

        population = self._evaluate_population(raw_population, generation=0)
        self.initial_population = raw_population
        self.evaluated_initial_population = list(population)
        self._record_generation(
            generation=0, population=population, selected=None, offspring=None,
            best=self._max_candidate(population),
        )

        self._store_experience(population, generation=0)

        self._log(f"3.5. INITIAL EVALUATION (best {self._max_candidate(population).overall_fitness:.1f}):")

        self.generation = 0
        self.evaluation_history = [c.overall_fitness for c in population]
        self.population_history.append(list(population))
        self.stagnation_counter = 0
        self.best_candidate = self._max_candidate(population)

        while self.generation < self.max_generations:
            self.generation += 1
            self._log(f"\n=== GENERATION {self.generation} ===")

            selected = self.selector.select(population, self.selection_count)
            self._log(f"4. SELECTED ARCHITECTURES: {len(selected.selected)} candidates")
            for s in selected.selected:
                self._log(f"   - {s.architecture.name} fitness={s.overall_fitness:.1f}")

            if self._check_stopping_condition(selected):
                self._log("Stopping condition met, terminating evolution.")
                self._record_generation(
                    generation=self.generation, population=population,
                    selected=selected.selected, offspring=[],
                    best=self._max_candidate(population),
                )
                break

            offspring_records: List[Dict[str, Any]] = []
            new_offspring: List[Candidate] = []
            for selected_candidate in selected.selected:
                mut_results = self.mutation_engine.mutate(
                    selected_candidate,
                    raw_requirement,
                    self.experience_memory if not self.use_llm else None,
                    application_type=self.application_type,
                    constraints=self.constraints,
                )
                for mut_result in mut_results:
                    mutated_candidate = self.fitness_engine.evaluate_and_score(
                        mut_result.new_architecture,
                        generation=self.generation,
                    )
                    mut_result.new_architecture.generation = self.generation
                    new_offspring.append(mutated_candidate)
                    offspring_records.append(
                        self._offspring_to_dict(mutated_candidate, mut_result)
                    )
                    self._log(
                        f"   Mutated: {mut_result.new_architecture.name} "
                        f"fitness={mutated_candidate.overall_fitness:.1f}"
                    )

            if not new_offspring:
                self._log("No offspring produced; stopping evolution.")
                self._record_generation(
                    generation=self.generation, population=population,
                    selected=selected.selected, offspring=[],
                    best=self._max_candidate(population),
                )
                break

            # Keep selected alongside offspring
            population = selected.selected + new_offspring
            population = self._evaluate_population(population, generation=self.generation)

            current_best = self._max_candidate(population)
            self._record_generation(
                generation=self.generation, population=population,
                selected=selected.selected, offspring=offspring_records,
                best=current_best,
            )

            self._store_experience(population, generation=self.generation)

            self._log(f"5. GENERATION {self.generation} EVALUATION (best {current_best.overall_fitness:.1f}):")
            for c in population:
                self._log(f"   {c}")

            self.population_history.append(list(population))

            # Track improvement / stagnation
            best_so_far = max(
                self.evaluation_history + [current_best.overall_fitness],
                default=0,
            )
            self.evaluation_history.append(current_best.overall_fitness)

            if current_best.overall_fitness > best_so_far:
                self.stagnation_counter = 0
                self.best_candidate = current_best
                self._log(
                    f"  ** Improvement! New best fitness: {current_best.overall_fitness:.1f}"
                )
            else:
                self.stagnation_counter += 1
                self._log(
                    f"  No improvement. Stagnation counter: "
                    f"{self.stagnation_counter}/{self.stagnation_limit}"
                )

            if self.stagnation_counter >= self.stagnation_limit:
                self._log(
                    f"Stopping: No improvement for {self.stagnation_limit} generations."
                )
                break

            if self.stopping_threshold and best_so_far >= self.stopping_threshold:
                self._log(
                    f"Stopping: Fitness threshold {self.stopping_threshold} reached."
                )
                break

        final_population = self._evaluate_population(population, generation=self.generation + 1)
        self.best_candidate = self._max_candidate(final_population)

        self._log(f"\n=== FINAL RESULTS ===")
        self._log(f"Best architecture: {self.best_candidate.architecture.name}")
        self._log(f"Best fitness: {self.best_candidate.overall_fitness:.1f}")

        return self._generate_results(
            raw_requirement,
            parsed,
            self.evaluated_initial_population,
            final_population,
            self.best_candidate,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _max_candidate(self, population: List[Candidate]) -> Candidate:
        return max(population, key=lambda c: c.overall_fitness)

    def _evaluate_population(
        self, population: List[Candidate], generation: int
    ) -> List[Candidate]:
        """Evaluate all candidates in a population."""
        evaluated = []
        for item in population:
            arch = item.architecture if hasattr(item, "architecture") else item
            candidate = self.fitness_engine.evaluate_and_score(arch, generation=generation)
            evaluated.append(candidate)
        return evaluated

    def _record_generation(
        self,
        generation: int,
        population: List[Candidate],
        selected: Optional[List[Candidate]],
        offspring: Optional[List[Dict[str, Any]]],
        best: Optional[Candidate],
    ) -> None:
        """Record rich detail for one generation in the evolution trace."""
        record: Dict[str, Any] = {
            "generation": generation,
            "population_size": len(population),
        }
        if best is not None:
            record["best_fitness"] = best.overall_fitness
            record["best_architecture"] = best.architecture.name
        record["population"] = [self._candidate_to_dict(c) for c in population]
        if selected is not None:
            record["selected"] = [self._candidate_to_dict(c) for c in selected]
        if offspring is not None:
            record["offspring"] = offspring
            for o in offspring:
                for exp in o.get("experience_used", []):
                    if exp not in self.experience_used:
                        self.experience_used.append(exp)
        self.generation_history.append(record)

    @staticmethod
    def _candidate_to_dict(c: Candidate) -> Dict[str, Any]:
        """Serialize a candidate for API output."""
        arch = c.architecture
        return {
            "name": arch.name,
            "generation": c.generation,
            "fitness": round(c.overall_fitness, 2),
            "objective_scores": {
                "cost": round(c.cost, 2),
                "security": round(c.security, 2),
                "reliability": round(c.reliability, 2),
                "performance": round(c.performance, 2),
                "scalability": round(c.scalability, 2),
            },
            "selected": bool(getattr(c, "selected_for_mutation", False)),
            "components": [
                {"name": comp.name, "type": comp.type, "quantity": comp.quantity,
                 "managed": comp.managed}
                for comp in arch.components
            ],
            "services": list(arch.services),
            "communication_pattern": arch.communication_pattern,
            "deployment_strategy": arch.deployment_strategy,
        }

    def _offspring_to_dict(
        self, candidate: Candidate, mutation_result: Any
    ) -> Dict[str, Any]:
        """Serialize an offspring with mutation provenance."""
        data = self._candidate_to_dict(candidate)
        data["source_architecture"] = (
            mutation_result.new_architecture.name
            if hasattr(mutation_result, "new_architecture") else ""
        )
        data["modifications"] = list(mutation_result.modifications)
        data["reasoning"] = mutation_result.reasoning
        data["source_weaknesses"] = list(mutation_result.source_weaknesses)
        data["experience_used"] = list(mutation_result.experience_used)
        return data

    def _store_experience(self, population: List[Candidate], generation: int) -> None:
        """Store experience from evaluated population."""
        best = self._max_candidate(population)
        objective_scores = {
            "cost": best.cost,
            "security": best.security,
            "reliability": best.reliability,
            "performance": best.performance,
            "scalability": best.scalability,
        }
        weaknesses = []
        if best.cost < 70:
            weaknesses.append("high cost")
        if best.security < 70:
            weaknesses.append("weak security")
        if best.reliability < 70:
            weaknesses.append("low reliability")
        if best.performance < 70:
            weaknesses.append("poor performance")
        if best.scalability < 70:
            weaknesses.append("limited scalability")

        req_context = getattr(best.architecture, "description", "") or ""

        self.experience_memory.add(
            architecture_name=best.architecture.name,
            generation=generation,
            objective_scores=objective_scores,
            fitness=best.overall_fitness,
            modifications=[],
            weaknesses=weaknesses,
            improvements=[],
            requirement_context=req_context,
        )

    def _check_stopping_condition(self, selected) -> bool:
        """Check if stopping condition is met."""
        if self.stopping_threshold:
            best_fitness = max(c.overall_fitness for c in selected.selected)
            if best_fitness >= self.stopping_threshold:
                return True
        return False

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def _generate_results(
        self,
        raw_requirement: str,
        parsed: Any,
        initial_population: List[Candidate],
        final_population: List[Candidate],
        best_candidate: Candidate,
    ) -> Dict[str, Any]:
        """Generate the complete results dictionary."""
        baseline = None
        if initial_population:
            baseline_result = evaluate_architecture(initial_population[0].architecture)
            baseline = {
                "cost": baseline_result.cost,
                "security": baseline_result.security,
                "reliability": baseline_result.reliability,
                "performance": baseline_result.performance,
                "scalability": baseline_result.scalability,
                "overall": baseline_result.overall,
            }

        final_scores = {
            "cost": best_candidate.cost,
            "security": best_candidate.security,
            "reliability": best_candidate.reliability,
            "performance": best_candidate.performance,
            "scalability": best_candidate.scalability,
            "overall": best_candidate.overall_fitness,
        }

        improvement = {}
        if baseline:
            for objective in ["cost", "security", "reliability", "performance", "scalability"]:
                if objective in baseline and objective in final_scores:
                    improvement[objective] = {
                        "initial": baseline[objective],
                        "final": final_scores[objective],
                        "absolute": final_scores[objective] - baseline[objective],
                        "percentage": (
                            (final_scores[objective] - baseline[objective])
                            / max(baseline[objective], 1e-10) * 100
                        ),
                    }

        arch = best_candidate.architecture
        initial_candidates = [
            self._candidate_to_dict(c) for c in initial_population
        ]

        total_candidates = self.population_size
        for gen in self.generation_history:
            total_candidates += len(gen.get("offspring", []))
        self.candidates_evaluated = total_candidates

        results = {
            "raw_requirement": raw_requirement,
            "application_type": self.application_type,
            "constraints": self.constraints,
            "parsed_requirements": {
                "functional": parsed.functional,
                "non_functional": parsed.non_functional,
                "expected_users": parsed.expected_users,
                "max_latency_ms": parsed.max_latency_ms,
                "availability_percentage": parsed.availability_percentage,
                "security_level": parsed.security_level,
                "data_encryption_required": parsed.data_encryption_required,
                "authentication_required": parsed.authentication_required,
                "scalability_type": parsed.scalability_type,
                "max_concurrent_streams": parsed.max_concurrent_streams,
                "cost_sensitive": parsed.cost_sensitive,
                "compliance_requirements": parsed.compliance_requirements,
                "deployment_environment": parsed.deployment_environment,
                "preferred_technologies": parsed.preferred_technologies,
                "max_monthly_cost": parsed.max_monthly_cost,
            },
            "baseline": baseline,
            "final_scores": final_scores,
            "improvement": improvement,
            "final_architecture": {
                "name": arch.name,
                "generation": arch.generation,
                "fitness": best_candidate.overall_fitness,
                "cost": best_candidate.cost,
                "security": best_candidate.security,
                "reliability": best_candidate.reliability,
                "performance": best_candidate.performance,
                "scalability": best_candidate.scalability,
                "overall_fitness": best_candidate.overall_fitness,
                "services": list(arch.services),
                "communication_pattern": arch.communication_pattern,
                "deployment_strategy": arch.deployment_strategy,
                "design_rationale": arch.design_rationale,
                "assumptions": list(arch.assumptions),
                "components": [
                    {"name": comp.name, "type": comp.type, "quantity": comp.quantity,
                     "managed": comp.managed}
                    for comp in arch.components
                ],
                "connections": derive_connections(
                    arch.components, arch.communication_pattern, arch.services
                ),
            },
            "final_scores": final_scores,
            "improvement": improvement,
            "initial_candidates": initial_candidates,
            "generation_history": self.generation_history,
            "evolution_history": {
                "generations_run": self.generation,
                "evaluation_history": self.evaluation_history,
                "population_size": self.population_size,
                "selection_count": self.selection_count,
                "mutation_count": self.mutation_count,
                "candidates_evaluated": self.candidates_evaluated,
                "fitness_progression": [
                    gen.get("best_fitness") for gen in self.generation_history
                ],
            },
            "experience_memory_entries": len(self.experience_memory.entries),
            "experience_used": self.experience_used,
        }

        return results

    def _log(self, message: str) -> None:
        """Log a message (can be overridden for CLI output)."""
        print(message)