from __future__ import annotations

import json
import csv
import os
import matplotlib.pyplot as plt
from typing import List, Dict, Any, Optional, Tuple, Union

from archevolve.requirements import parse_requirement
from archevolve.generation.architecture_generator import ArchitectureGenerator
from archevolve.evaluation import evaluate_architecture
from archevolve.fitness.fitness_engine import FitnessEngine, Candidate
from archevolve.selection.selector import Selector, SelectionResult
from archevolve.evolution.evolution_engine import EvolutionEngine
from archevolve.memory.experience_memory import JsonExperienceMemory


class ExperimentConfig:
    """Configuration for running experiments."""

    def __init__(
        self,
        population_size: int = 5,
        max_generations: int = 5,
        selection_count: int = 2,
        mutation_count: int = 2,
        weights: Optional[Dict[str, float]] = None,
        use_llm: bool = False,
        stopping_threshold: Optional[float] = None,
    ):
        self.population_size = population_size
        self.max_generations = max_generations
        self.selection_count = selection_count
        self.mutation_count = mutation_count
        self.weights = weights or {
            "cost": 0.20,
            "security": 0.20,
            "reliability": 0.20,
            "performance": 0.20,
            "scalability": 0.20,
        }
        self.use_llm = use_llm
        self.stopping_threshold = stopping_threshold


class ExperimentResults:
    """Holds and manages experiment results data."""

    def __init__(self):
        self.scenarios: List[Dict[str, Any]] = []

    def add_scenario(self, results: Dict[str, Any]) -> None:
        """Add a scenario's results."""
        self.scenarios.append(results)

    def to_csv(self, filepath: str) -> None:
        """Export all scenarios to CSV."""
        if not self.scenarios:
            return
        all_keys = set()
        for s in self.scenarios:
            all_keys.update(s.keys())
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
            writer.writeheader()
            for s in self.scenarios:
                writer.writerow(s)

    def to_json(self, filepath: str) -> None:
        """Export all scenarios to JSON."""
        with open(filepath, "w") as f:
            json.dump(self.scenarios, f, indent=2)

    def plot_fitness_vs_generation(self, output_path: str = "fitness_vs_generation.png") -> None:
        """Plot fitness vs generation for all scenarios."""
        if not self.scenarios:
            return
        how_many = len(self.scenarios)
        fig, axes = plt.subplots(
            min(how_many, 4), 2, figsize=(12, 5 * min(how_many, 4) / 2)
        )
        fig.suptitle("Fitness vs Generation by Scenario")

        for idx, scenario in enumerate(self.scenarios):
            gen_range = scenario.get("evolution_history", {}).get(
                "evaluation_history", []
            )
            if not gen_range:
                continue
            ax = axes[idx // 2, idx % 2] if how_many > 1 else axes[idx]

            all_fitness = [scenario.get("baseline", {}).get("overall", 0)] + gen_range
            all_gens = list(range(len(all_fitness)))

            ax.plot(all_gens, all_fitness, "b-o", linewidth=2, markersize=4)
            ax.set_xlabel("Generation")
            ax.set_ylabel("Fitness")
            ax.set_title(
                f"Scenario {idx + 1}: {scenario.get('raw_requirement', '')[:40]}..."
            )
            ax.grid(True, alpha=0.3)
            ax.set_ylim(0, 100)

        for idx in range(len(self.scenarios), min(how_many, 4) * 2):
            row, col = divmod(idx, 2)
            if row < 4:
                fig.delaxes(axes[row, col] if how_many > 1 else axes[idx])

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()

    def plot_objective_comparison(
        self, output_path: str = "objective_comparison.png"
    ) -> None:
        """Plot objective scores before after evolution."""
        if not self.scenarios:
            return
        objectives = ["cost", "security", "reliability", "performance", "scalability"]
        fig, ax = plt.subplots(figsize=(12, 6))
        width = 0.35
        baseline_means = {}
        final_means = {}
        for obj in objectives:
            baseline_vals = []
            final_vals = []
            for s in scenarios:
                b = s.get("baseline", {})
                f = s.get("final_scores", {})
                baseline_vals.append(b.get(obj, 0))
                final_vals.append(f.get(obj, 0))
            baseline_means[obj] = sum(baseline_vals) / len(baseline_vals) if baseline_vals else 0
            final_means[obj] = sum(final_vals) / len(final_vals) if final_vals else 0
        x = range(len(objectives))
        ax.bar(
            [i - width / 2 for i in x],
            baseline_means.values(),
            width,
            label="Baseline",
            alpha=0.7,
            color="steelblue",
        )
        ax.bar(
            [i + width / 2 for i in x],
            final_means.values(),
            width,
            label="ARCHEVOLVE",
            alpha=0.7,
            color="darkgreen",
        )
        ax.set_xlabel("Objectives")
        ax.set_ylabel("Score (0-100)")
        ax.set_title("Objective Scores: Baseline vs ARCHEVOLVE")
        ax.set_xticks(x)
        ax.set_xticklabels(objectives)
        ax.legend()
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3, linestyle="--")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()

    def plot_baseline_vs_arch_evolve(
        self, output_path: str = "baseline_vs_arch_evolve.png"
    ) -> None:
        """Plot baseline vs ARCHEVOLVE fitness comparison."""
        if not self.scenarios:
            return
        fig, ax = plt.subplots(figsize=(10, 6))
        scenario_names = []
        baseline_fitness = []
        arch_evolve_fitness = []
        for s in scenarios:
            b = s.get("baseline", {}).get("overall", 0)
            f = s.get("final_scores", {}).get("overall", 0)
            scenario_names.append(
                s.get("raw_requirement", "")[:30].replace("\n", " ")
            )
            baseline_fitness.append(b)
            arch_evolve_fitness.append(f)
        x = range(len(scenario_names))
        ax.bar(
            [i - width / 2 for i in x],
            baseline_fitness,
            width,
            label="Baseline",
            alpha=0.7,
            color="steelblue",
        )
        ax.bar(
            [i + width / 2 for i in x],
            arch_evolve_fitness,
            width,
            label="ARCHEVOLVE",
            alpha=0.7,
            color="darkgreen",
        )
        ax.set_xlabel("Scenarios")
        ax.set_ylabel("Fitness Score")
        ax.set_title("Baseline vs ARCHEVOLVE Fitness Comparison")
        ax.set_xticks(x)
        ax.set_xticklabels(
            [f"'{name}'" for name in scenario_names], rotation=45, ha="right"
        )
        ax.legend()
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3, linestyle="--")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()


class ExperimentRunner:
    """Runs reproducible experiments comparing Baseline vs ARCHEVOLVE."""

    def __init__(self, config: ExperimentConfig):
        self.config = config

    def _run_baseline(self, raw_requirement: str) -> Dict[str, Any]:
        """Run baseline: single monolith generated without evolutionary optimization."""
        from archevolve.models.architecture import ArchitectureModel
        parsed = parse_requirement(raw_requirement)
        architecture = ArchitectureModel.create_monolith(
            {
                "expected_users": parsed.expected_users or 1000,
                "security_level": parsed.security_level or "medium",
                "cost_sensitive": parsed.cost_sensitive,
                "deployment_env": parsed.deployment_environment or "cloud",
            }
        )
        fitness_result = evaluate_architecture(architecture)
        return {
            "raw_requirement": raw_requirement,
            "architecture_name": architecture.name,
            "cost": fitness_result.cost,
            "security": fitness_result.security,
            "reliability": fitness_result.reliability,
            "performance": fitness_result.performance,
            "scalability": fitness_result.scalability,
            "overall": fitness_result.overall,
            "objective_reasoning": {
                "cost": fitness_result.cost_reasoning,
                "security": fitness_result.security_reasoning,
                "reliability": fitness_result.reliability_reasoning,
                "performance": fitness_result.performance_reasoning,
                "scalability": fitness_result.scalability_reasoning,
            },
        }

    def _run_arch_evolve(
        self, raw_requirement: str, application_type: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run ARCHEVOLVE: evolutionary process generating optimized architecture."""
        engine = EvolutionEngine(
            population_size=self.config.population_size,
            max_generations=self.config.max_generations,
            selection_count=self.config.selection_count,
            mutation_count=self.config.mutation_count,
            weights=self.config.weights,
            use_llm=self.config.use_llm,
            stopping_threshold=self.config.stopping_threshold,
            application_type=application_type or "",
            constraints=constraints or {},
        )
        results = engine.run(raw_requirement)
        return {
            "raw_requirement": raw_requirement,
            "architecture_name": results.get("final_architecture", {}).get(
                "name", "unknown"
            ),
            "generations_run": results.get("evolution_history", {}).get(
                "generations_run", 0
            ),
            "cost": results.get("final_scores", {}).get("cost", 0),
            "security": results.get("final_scores", {}).get("security", 0),
            "reliability": results.get("final_scores", {}).get("reliability", 0),
            "performance": results.get("final_scores", {}).get("performance", 0),
            "scalability": results.get("final_scores", {}).get("scalability", 0),
            "overall": results.get("final_scores", {}).get("overall", 0),
            "baseline_overall": results.get("baseline", {}).get("overall", None) if False else 0,
            "improvement": results.get("improvement", {}),
            "evolution_history": results.get("evolution_history", {}),
            "experience_memory_entries": results.get(
                "experience_memory_entries", 0
            ),
        }

    def run_scenario(
        self,
        raw_requirement: str,
        application_type: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run a single scenario: both Baseline and ARCHEVOLVE.

        Args:
            raw_requirement: Free-text system requirements
            application_type: Optional application/system type for domain-aware design
            constraints: Optional structured constraints

        Returns:
            Combined baseline + ARCHEVOLVE results
        """
        # Run baseline (naive monolith without evolutionary optimization)
        baseline = self._run_baseline(raw_requirement)

        # Run ARCHEVOLVE
        arch_evolve = self._run_arch_evolve(
            raw_requirement, application_type, constraints
        )

        # Combine results
        combined = {
            "raw_requirement": raw_requirement,
            "application_type": application_type or "",
            "baseline": baseline,
            "arch_evolve": arch_evolve,
        }

        # Calculate improvements
        if baseline.get("overall") and arch_evolve.get("overall"):
            baseline_overall = baseline["overall"]
            arch_overall = arch_evolve["overall"]
            combined["absolute_improvement"] = arch_overall - baseline_overall
            combined["percentage_improvement"] = (
                (arch_overall - baseline_overall) / max(baseline_overall, 1e-10) * 100
            )
            # Objective-wise improvements
            improvements = {}
            for obj in ["cost", "security", "reliability", "performance", "scalability"]:
                b = baseline.get(obj, 0)
                a = arch_evolve.get(obj, 0)
                improvements[obj] = {
                    "initial": b,
                    "final": a,
                    "absolute": a - b,
                    "percentage": (a - b) / max(b, 1e-10) * 100,
                }
            combined["objective_improvements"] = improvements

        return combined

    def run_experiments(
        self,
        scenarios: List[Union[str, Dict[str, Any], List[Any]]],
    ) -> ExperimentResults:
        """Run experiments for multiple scenarios.

        Each scenario may be:
          * a plain requirement string (application type auto-detected),
          * a dict: {"requirement": ..., "application_type": ..., "constraints": ...},
          * a list/tuple: [requirement, application_type, constraints]

        Returns:
            ExperimentResults containing per-scenario baseline + ARCHEVOLVE runs.
        """
        results = ExperimentResults()
        for scenario in scenarios:
            requirement, app_type, constraints = self._normalize_scenario(scenario)
            scenario_results = self.run_scenario(requirement, app_type, constraints)
            results.add_scenario(scenario_results)
        return results

    @staticmethod
    def _normalize_scenario(scenario: Any) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
        """Normalize a scenario definition into (requirement, app_type, constraints)."""
        if isinstance(scenario, dict):
            return (
                scenario.get("requirement", "") or "",
                scenario.get("application_type"),
                scenario.get("constraints"),
            )
        if isinstance(scenario, (list, tuple)):
            padded = list(scenario) + [None, None]
            return str(padded[0]), padded[1], padded[2]
        return str(scenario), None, None

    @staticmethod
    def _log(msg: str) -> None:
        print(f"[Experiment] {msg}")