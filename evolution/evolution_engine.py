from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import List, Dict, Any, Optional

from ..requirements import parse_requirement
from ..generation.architecture_generator import ArchitectureGenerator
from ..evaluation import evaluate_architecture
from ..fitness.fitness_engine import FitnessEngine, Candidate
from ..selection.selector import Selector, SelectionResult
from ..mutation.mutation_engine import MutationEngine, MutationResult
from ..memory.experience_memory import JsonExperienceMemory


class EvolutionEngine:
    """Complete evolutionary engine for architecture design.

    Orchestrates the full generate-evaluate-evolve loop inspired by AlphaEvolve.

    Pseudo-flow:
        parse requirements
        population = generate_initial_population(requirements)
        for generation in range(MAX_GENERATIONS):
            evaluate(population)
            rank(population)
            selected = select_top_candidates(population)
            store_experience(selected)
            if stopping_condition:
                break
            offspring = mutate(selected, requirements, experience_memory)
            population = selected + offspring
        evaluate final population
        best = select_best_architecture()
        generate report
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
    ):
        """Initialize evolution engine.

        Args:
            population_size: Number of candidate architectures per generation
            max_generations: Maximum number of generations to evolve
            selection_count: Number of top candidates to retain for mutation
            mutation_count: Number of mutated architectures to produce
            weights: Fitness function weights (cost, security, reliability, performance, scalability)
            use_llm: Whether to use LLM for mutation (deterministic fallback if False)
            experience_path: Path for experience memory persistence
            stopping_threshold: Stop if overall_fitness reaches this value
            stagnation_limit: Stop if no improvement for N generations
        """
        self.population_size = population_size
        self.max_generations = max_generations
        self.selection_count = selection_count
        self.mutation_count = mutation_count
        self.use_llm = use_llm
        self.stagnation_limit = stagnation_limit

        # Fitness engine with configurable weights
        self.fitness_engine = FitnessEngine(weights=weights)

        # Selection mechanism
        self.selector = Selector()

        # Mutation engine
        self.mutation_engine = MutationEngine(use_llm=use_llm, mutation_count=mutation_count)

        # Experience memory
        self.experience_memory = JsonExperienceMemory(experience_path)

        # Tracking variables
        self.generation = 0
        self.evaluation_history: List[float] = []
        self.population_history: List[List[Candidate]] = []
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
        # Step 1: Parse requirements
        parsed = parse_requirement(raw_requirement)
        self._log(f"1. REQUIREMENTS: {raw_requirement}")
        self._log(f"2. PARSED REQUIREMENTS: {parsed.raw_input}")

        # Step 2: Generate initial population
        generator = ArchitectureGenerator(
            population_size=self.population_size, seed=42
        )
        population = generator.generate_initial_population(raw_requirement)
        self.initial_population = population
        self._log(f"3. INITIAL POPULATION: {len(population)} candidates")

        # Evaluate each candidate in initial population
        population = self._evaluate_population(population, generation=0)

        # Store initial experience
        self._store_experience(population, generation=0)

        self._log(f"3.5. INITIAL EVALUATION:")
        for c in population:
            self._log(f"   {c}")

        # Evolutionary loop
        self.generation = 0
        self.evaluation_history = [c.overall_fitness for c in population]
        self.population_history.append(list(population))
        self.stagnation_counter = 0
        self.best_candidate = max(population, key=lambda c: c.overall_fitness)

        while self.generation < self.max_generations:
            self.generation += 1
            self._log(f"\n=== GENERATION {self.generation} ===")

            # Selection: select top candidates
            selected = self.selector.select(
                population, self.selection_count
            )
            self._log(f"4. SELECTED ARCHITECTURES: {len(selected.selected)} candidates")

            for s in selected.selected:
                self._log(f"   - {s.architecture.name} fitness={s.overall_fitness:.1f}")

            # Check stopping condition before mutation
            if self._check_stopping_condition(selected):
                self._log("Stopping condition met, terminating evolution.")
                break

            # Mutation: produce offspring from selected candidates
            offspring = []
            for selected_candidate in selected.selected:
                mut_results = self.mutation_engine.mutate(
                    selected_candidate,
                    raw_requirement,
                    self.experience_memory if not self.use_llm else None,
                )
                for mut_result in mut_results:
                    # Evaluate the new architecture
                    mutated_candidate = self.fitness_engine.evaluate_and_score(
                        mut_result.new_architecture, generation=self.generation
                    )
                    offspring.append(mutated_candidate)
                    self._log(
                        f"   Mutated: {mut_result.new_architecture.name} "
                        f"fitness={mutated_candidate.overall_fitness:.1f}"
                    )

            # Combine selected + offspring for next generation
            population = selected.selected + offspring

            # Evaluate the new population
            population = self._evaluate_population(population, generation=self.generation)

            # Store experience
            self._store_experience(population, generation=self.generation)

            self._log(f"5. GENERATION {self.generation} EVALUATION:")
            for c in population:
                self._log(f"   {c}")

            # Track history
            self.population_history.append(list(population))

            # Check for improvement
            current_best = max(population, key=lambda c: c.overall_fitness)
            best_so_far = max(
                self.evaluation_history + [current_best.overall_fitness],
                default=0,
            )

            self.evaluation_history.append(current_best.overall_fitness)

            if current_best.overall_fitness > best_so_far:
                self.stagnation_counter = 0
                self.best_candidate = current_best
                self._log(
                    f"  ** Improvement! New best fitness: {current_best.overall_fitness:.1f} "
                )
            else:
                self.stagnation_counter += 1
                self._log(
                    f"  No improvement. Stagnation counter: {self.stagnation_counter}/{self.stagnation_limit}"
                )

            if self.stagnation_counter >= self.stagnation_limit:
                self._log(
                    f"Stopping: No improvement for {self.stagnation_limit} generations."
                )
                break

            # Check threshold
            if self.stopping_threshold and best_so_far >= self.stopping_threshold:
                self._log(
                    f"Stopping: Fitness threshold {self.stopping_threshold} reached."
                )
                break

        # Final result selection
        final_population = self._evaluate_population(
            population, generation=self.generation + 1
        )
        self.best_candidate = max(final_population, key=lambda c: c.overall_fitness)

        self._log(f"\n=== FINAL RESULTS ===")
        self._log(f"Best architecture: {self.best_candidate.architecture.name}")
        self._log(f"Best fitness: {self.best_candidate.overall_fitness:.1f}")

        # Generate results dictionary
        results = self._generate_results(
            raw_requirement, parsed, self.initial_population,
            final_population, self.best_candidate
        )

        return results

    def _evaluate_population(
        self, population: List[Candidate], generation: int
    ) -> List[Candidate]:
        """Evaluate all candidates in a population.

        Args:
            population: List of candidates to evaluate
            generation: Current generation number

        Returns:
            List of candidates with fitness scores computed
        """
        evaluated = []
        for item in population:
            # Handle both Architecture and Candidate objects
            arch = item.architecture if hasattr(item, 'architecture') else item
            candidate = self.fitness_engine.evaluate_and_score(
                arch, generation=generation
            )
            evaluated.append(candidate)
        return evaluated

    def _store_experience(
        self, population: List[Candidate], generation: int
    ) -> None:
        """Store experience from evaluated population.

        Args:
            population: Evaluated population
            generation: Current generation number
        """
        # Store the best candidate's experience
        best = max(population, key=lambda c: c.overall_fitness)
        objective_scores = {
            "cost": best.cost,
            "security": best.security,
            "reliability": best.reliability,
            "performance": best.performance,
            "scalability": best.scalability,
        }

        # Extract weaknesses from low scores
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

        # Determine requirement context
        from ..requirements import parse_requirement
        parsed = parse_requirement(best.architecture.name if hasattr(best.architecture, 'name') else '')

        req_context = getattr(best.architecture, 'description', '') or ''

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

    def _check_stopping_condition(
        self, selected: SelectionResult
    ) -> bool:
        """Check if stopping condition is met.

        Args:
            selected: Selection result from current generation

        Returns:
            True if stopping condition met
        """
        # Check threshold
        if self.stopping_threshold:
            best_fitness = max(c.overall_fitness for c in selected.selected)
            if best_fitness >= self.stopping_threshold:
                return True

        # Check stagnation (need history for this, so simplified)
        return False

    def _generate_results(
        self,
        raw_requirement: str,
        parsed: Any,
        initial_population: Any,
        final_population: List[Candidate],
        best_candidate: Candidate,
    ) -> Dict[str, Any]:
        """Generate results dictionary.

        Args:
            raw_requirement: Original requirement text
            parsed: Parsed requirement model
            initial_population: First generation architectures
            final_population: Final generation candidates
            best_candidate: Best candidate from final generation

        Returns:
            Dictionary with all results
        """
        # Baseline: first architecture from initial population
        baseline = None
        if initial_population:
            from ..evaluation import evaluate_architecture
            baseline_result = evaluate_architecture(initial_population[0])
            baseline = {
                "cost": baseline_result.cost,
                "security": baseline_result.security,
                "reliability": baseline_result.reliability,
                "performance": baseline_result.performance,
                "scalability": baseline_result.scalability,
                "overall": baseline_result.overall,
            }

        # Final architecture scores
        final_scores = {
            "cost": best_candidate.cost,
            "security": best_candidate.security,
            "reliability": best_candidate.reliability,
            "performance": best_candidate.performance,
            "scalability": best_candidate.scalability,
            "overall": best_candidate.overall_fitness,
        }

        # Improvement calculations
        improvement = {}
        if baseline:
            for objective in ["cost", "security", "reliability", "performance", "scalability"]:
                if objective in baseline and objective in final_scores:
                    improvement[objective] = {
                        "initial": baseline[objective],
                        "final": final_scores[objective],
                        "absolute": final_scores[objective] - baseline[objective],
                        "percentage": (
                            (final_scores[objective] - baseline[objective]) / max(baseline[objective], 1e-10) * 100
                        ),
                    }

        results = {
            "raw_requirement": raw_requirement,
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
            },
            "initial_population": [
                {
                    "name": (
                        c.name if hasattr(c, 'name') else (c.architecture.name if hasattr(c, 'architecture') else str(c))
                    ),
                    "generation": (
                        c.generation if hasattr(c, 'generation') else 0
                    ),
                    "components": [
                        {
                            "name": comp.name if hasattr(comp, 'name') else comp.get("name", "unknown")
                            if isinstance(comp, dict)
                            else comp.name
                        }
                        for comp in (
                            c.components if hasattr(c, 'components') else c.get("components", [])
                        )
                    ],
                }
                for c in initial_population
            ]
            if initial_population
            else [],

            "baseline": baseline,
            "final_architecture": {
                "name": best_candidate.architecture.name,
                "generation": best_candidate.generation,
                "cost": best_candidate.cost,
                "security": best_candidate.security,
                "reliability": best_candidate.reliability,
                "performance": best_candidate.performance,
                "scalability": best_candidate.scalability,
                "overall_fitness": best_candidate.overall_fitness,
                "components": [
                    {"name": comp.name, "type": comp.type, "managed": comp.managed}
                    for comp in best_candidate.architecture.components
                ],
            },
            "final_scores": final_scores,
            "improvement": improvement,
            "evolution_history": {
                "generations_run": self.generation,
                "evaluation_history": self.evaluation_history,
                "population_size": self.population_size,
                "selection_count": self.selection_count,
                "mutation_count": self.mutation_count,
            },
            "experience_memory_entries": len(self.experience_memory.entries),
        }

        return results

    def _log(self, message: str) -> None:
        """Log a message (can be overridden for CLI output)."""
        print(message)