from __future__ import annotations

import json
import random
from typing import List, Dict, Any, Optional

from ..models.architecture import Architecture, Component
from ..fitness.fitness_engine import FitnessEngine, Candidate


class MutationResult:
    """Result from a mutation operation."""

    def __init__(
        self,
        new_architecture: Architecture,
        modifications: List[str],
        reasoning: str,
        source_weaknesses: List[str] = None,
    ):
        self.new_architecture = new_architecture
        self.modifications = modifications
        self.reasoning = reasoning
        self.source_weaknesses = source_weaknesses or []

    def __str__(self) -> str:
        lines = ["Mutation Result:"]
        lines.append(f"  Reasoning: {self.reasoning}")
        if self.modifications:
            lines.append("  Modifications:")
            for m in self.modifications:
                lines.append(f"    - {m}")
        return "\n".join(lines)


class ExperienceEntry:
    """A single experience entry stored in experience memory."""

    def __init__(
        self,
        architecture_name: str,
        generation: int,
        objective_scores: Dict[str, float],
        fitness: float,
        modifications: List[str],
        weaknesses: List[str],
        improvements: List[str],
        requirement_context: Dict[str, Any],
    ):
        self.architecture_name = architecture_name
        self.generation = generation
        self.objective_scores = objective_scores
        self.fitness = fitness
        self.modifications = modifications
        self.weaknesses = weaknesses
        self.improvements = improvements
        self.requirement_context = requirement_context

    def __str__(self) -> str:
        lines = [
            f"Experience: {self.architecture_name} gen-{self.generation}",
            f"  Fitness: {self.fitness:.1f}",
            f"  Weaknesses: {', '.join(self.weaknesses)}",
            f"  Improvements: {', '.join(self.improvements)}",
        ]
        return "\n".join(lines)


class MutationEngine:
    """LLM-assisted mutation/evolution of architectures."""

    def __init__(
        self,
        use_llm: bool = False,
        mutation_count: int = 2,
    ):
        """Initialize mutation engine.

        Args:
            use_llm: Whether to use LLM for mutation (requires API key)
            mutation_count: Number of mutated architectures to produce
        """
        self.use_llm = use_llm
        self.mutation_count = mutation_count
        self.rng = random.Random(42)

        # Pre-defined mutation patterns based on experience
        self.mutation_patterns = self._init_mutation_patterns()

    def _init_mutation_patterns(self) -> Dict[str, Any]:
        """Initialize predefined mutation patterns for deterministic mode."""
        return {
            "add_cache": {
                "description": "Add Redis cache to improve performance",
                "target_objectives": ["performance", "scalability"],
                "apply": self._mutate_add_cache,
            },
            "remove_service": {
                "description": "Consolidate services to reduce cost",
                "target_objectives": ["cost"],
                "apply": self._mutate_remove_service,
            },
            "add_messaging": {
                "description": "Add message broker for decoupling",
                "target_objectives": ["reliability", "scalability"],
                "apply": self._mutate_add_messaging,
            },
            "managed_to_unmanaged": {
                "description": "Switch from managed to unmanaged services",
                "target_objectives": ["cost"],
                "apply": self._mutate_managed_to_unmanaged,
            },
            "add_gateway": {
                "description": "Add API gateway for security",
                "target_objectives": ["security"],
                "apply": self._mutate_add_gateway,
            },
        }

    def mutate(
        self,
        candidate: Candidate,
        requirements: str,
        experience_memory: Optional["ExperienceMemory"] = None,
    ) -> List[MutationResult]:
        """Produce mutated architectures from a selected candidate.

        Args:
            candidate: The selected candidate to mutate
            requirements: Original requirement text
            experience_memory: Optional experience memory for context

        Returns:
            List of MutationResult objects
        """
        # Parse requirements for context
        from ..requirements import parse_requirement
        parsed = parse_requirement(requirements)

        # Gather weakness information from evaluation
        weaknesses = self._identify_weaknesses(candidate)

        # Use experience memory if available
        experience_context = {}
        if experience_memory:
            entries = experience_memory.recent_entries(
                min_score=candidate.overall_fitness,
                limit=3,
            )
            if entries:
                experience_context = {
                    "previous_experiences": [str(e) for e in entries],
                    "requirement_context": parsed.raw_input,
                }

        # Determine which mutation patterns to apply
        target_objectives = self._prioritize_weaknesses(
            candidate, experience_context
        )

        # Apply mutations
        results = []
        applied_patterns = set()

        while len(results) < self.mutation_count and self.mutation_patterns:
            # Pick a pattern that targets weak objectives
            pattern_name = self._select_mutation_pattern(
                target_objectives, applied_patterns
            )

            if pattern_name not in self.mutation_patterns:
                break

            pattern = self.mutation_patterns[pattern_name]
            applied_patterns.add(pattern_name)

            # Apply the mutation
            new_arch = pattern["apply"](
                candidate.architecture, parsed, experience_context
            )

            # Evaluate the new architecture
            engine = FitnessEngine()
            fitness_result = engine.evaluate_and_score(new_arch, candidate.generation + 1)

            # Build modifications list
            modifications = self._generate_modifications(
                pattern, candidate, fitness_result
            )

            # Build reasoning
            reasoning = self._generate_reasoning(
                pattern, candidate, fitness_result, weaknesses
            )

            result = MutationResult(
                new_architecture=new_arch,
                modifications=modifications,
                reasoning=reasoning,
                source_weaknesses=weaknesses,
            )
            results.append(result)

        return results

    def _identify_weaknesses(self, candidate: Candidate) -> List[str]:
        """Identify weak evaluation objectives for a candidate."""
        weaknesses = []
        scores = {
            "cost": candidate.cost,
            "security": candidate.security,
            "reliability": candidate.reliability,
            "performance": candidate.performance,
            "scalability": candidate.scalability,
        }

        # Find lowest-scoring objectives
        sorted_objectives = sorted(scores.items(), key=lambda x: x[1])

        for obj_name, score in sorted_objectives[:2]:  # bottom 2
            if score < 70:
                weaknesses.append(f"low {obj_name} ({score:.1f})")

        if not weaknesses:
            weaknesses = ["no significant weaknesses identified"]

        return weaknesses

    def _prioritize_weaknesses(
        self, candidate: Candidate, experience_context: Dict[str, Any]
    ) -> List[str]:
        """Prioritize mutation targets based on weaknesses and experience."""
        scores = {
            "cost": candidate.cost,
            "security": candidate.security,
            "reliability": candidate.reliability,
            "performance": candidate.performance,
            "scalability": candidate.scalability,
        }

        # Sort by score (ascending - weakest first)
        prioritized = sorted(scores.items(), key=lambda x: x[1])

        # Return objective names from weakest to strongest
        return [obj_name for obj_name, _ in prioritized]

    def _select_mutation_pattern(
        self, target_objectives: List[str], applied: set
    ) -> Optional[str]:
        """Select a mutation pattern targeting the given objectives.

        Args:
            target_objectives: List of objective names ordered by weakness
            applied: Set of already-applied pattern names

        Returns:
            Pattern name or None if no applicable pattern
        """
        # Try patterns that target the weakest objectives first
        objective = target_objectives[0] if target_objectives else None

        # Map objectives to relevant patterns
        objective_to_patterns = {
            "cost": ["remove_service", "managed_to_unmanaged"],
            "security": ["add_gateway"],
            "reliability": ["add_messaging"],
            "performance": ["add_cache"],
            "scalability": ["add_messaging", "add_cache"],
        }

        # Find patterns for the weakest objective
        relevant_patterns = objective_to_patterns.get(objective, [])

        # Filter out already-applied patterns
        available = [p for p in relevant_patterns if p not in applied]

        if not available:
            # Try any unapplied pattern
            all_unapplied = [
                p for p in self.mutation_patterns.keys() if p not in applied
            ]
            return all_unapplied[0] if all_unapplied else None

        return available[0]

    # --- Concrete mutation application methods ---

    def _mutate_add_cache(
        self, architecture: Architecture, parsed: Any, context: Dict[str, Any]
    ) -> Architecture:
        """Add Redis cache to improve performance and scalability."""
        comps = list(architecture.components)

        # Add Redis cache if not present
        if not any(c.type == "cache" for c in comps):
            comps.append(
                Component(name="Redis", type="cache", managed=True)
            )
        else:
            # Enhance existing cache
            for c in comps:
                if c.type == "cache":
                    c.managed = True
                    c.properties["enabled"] = True

        new_arch = Architecture(
            name=f"{architecture.name} with Cache",
            generation=architecture.generation + 1,
            components=comps,
            services=architecture.services,
            deployment_strategy=architecture.deployment_strategy,
            communication_pattern=architecture.communication_pattern,
            design_rationale=architecture.design_rationale,
            assumptions=architecture.assumptions,
        )
        return new_arch

    def _mutate_remove_service(self, architecture: Architecture, parsed: Any, context: Dict[str, Any]) -> Architecture:
        """Consolidate services to reduce cost."""
        comps = list(architecture.components)

        # Remove a service component (not gateway, database, or cache)
        service_comps = [c for c in comps if c.type == "service"]
        if service_comps:
            # Remove one service (randomly chosen via rng)
            comps_to_remove = self.rng.choice(service_comps)
            comps = [c for c in comps if c.name != comps_to_remove.name]

        new_arch = Architecture(
            name=f"{architecture.name} (Consolidated)",
            generation=architecture.generation + 1,
            components=comps,
            services=architecture.services,
            deployment_strategy=architecture.deployment_strategy,
            communication_pattern=architecture.communication_pattern,
            design_rationale=architecture.design_rationale,
            assumptions=architecture.assumptions,
        )
        return new_arch

    def _mutate_add_messaging(self, architecture: Architecture, parsed: Any, context: Dict[str, Any]) -> Architecture:
        """Add message broker for decoupling."""
        comps = list(architecture.components)

        # Add RabbitMQ if not present
        if not any(c.type == "messaging" for c in comps):
            comps.append(
                Component(name="RabbitMQ", type="messaging", managed=False)
            )

        new_arch = Architecture(
            name=f"{architecture.name} with Messaging",
            generation=architecture.generation + 1,
            components=comps,
            services=architecture.services,
            deployment_strategy=architecture.deployment_strategy,
            communication_pattern="event-driven",
            design_rationale=architecture.design_rationale,
            assumptions=architecture.assumptions,
        )
        return new_arch

    def _mutate_managed_to_unmanaged(self, architecture: Architecture, parsed: Any, context: Dict[str, Any]) -> Architecture:
        """Switch from managed to unmanaged services to reduce cost."""
        comps = list(architecture.components)

        # Convert managed services to unmanaged (except gateways and databases)
        for c in comps:
            if c.managed and c.type not in ("gateway", "database"):
                c.managed = False

        new_arch = Architecture(
            name=f"{architecture.name} (Unmanaged)",
            generation=architecture.generation + 1,
            components=comps,
            services=architecture.services,
            deployment_strategy=architecture.deployment_strategy,
            communication_pattern=architecture.communication_pattern,
            design_rationale=architecture.design_rationale,
            assumptions=architecture.assumptions,
        )
        return new_arch

    def _mutate_add_gateway(self, architecture: Architecture, parsed: Any, context: Dict[str, Any]) -> Architecture:
        """Add API gateway for security."""
        comps = list(architecture.components)

        # Add API gateway if not present
        if not any(c.type == "gateway" for c in comps):
            comps.append(
                Component(name="API Gateway", type="gateway", managed=True)
            )

        new_arch = Architecture(
            name=f"{architecture.name} with Gateway",
            generation=architecture.generation + 1,
            components=comps,
            services=architecture.services,
            deployment_strategy=architecture.deployment_strategy,
            communication_pattern=architecture.communication_pattern,
            design_rationale=architecture.design_rationale,
            assumptions=architecture.assumptions,
        )
        return new_arch

    def _generate_modifications(
        self, pattern: Any, candidate: Candidate, fitness_result: Any
    ) -> List[str]:
        """Generate human-readable modification descriptions."""
        modifications = []

        pattern_name = pattern["description"] if isinstance(pattern, dict) else pattern["description"]

        # Add fitness-based modification
        modifications.append(
            f"Applied: {pattern_name} "
            f"-> improved {fitness_result.overall_fitness:.1f} fitness"
        )

        return modifications

    def _generate_reasoning(
        self, pattern: Any, candidate: Candidate, fitness_result: Any, weaknesses: List[str]
    ) -> str:
        """Generate reasoning for the mutation."""
        objective = pattern["target_objectives"][0] if isinstance(pattern, dict) else pattern["target_objectives"][0]

        reason_parts = [
            f"Mutation applied targeting weak {objective} objective.",
            f"Previous fitness: {candidate.overall_fitness:.1f}, "
            f"New fitness: {fitness_result.overall_fitness:.1f}",
        ]

        # Add weakness context
        if weaknesses:
            reason_parts.append(
                f"Identified weaknesses: {', '.join(weaknesses)}"
            )

        return " ".join(reason_parts)