from __future__ import annotations

import random
from typing import List, Dict, Any, Optional, Set

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
        experience_used: List[str] = None,
    ):
        self.new_architecture = new_architecture
        self.modifications = modifications
        self.reasoning = reasoning
        self.source_weaknesses = source_weaknesses or []
        self.experience_used = experience_used or []

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
        return (
            f"{self.architecture_name} achieved fitness {self.fitness:.1f}; "
            f"weaknesses: {', '.join(self.weaknesses) or 'none'}; "
            f"improvements: {', '.join(self.improvements)}"
        )


class MutationEngine:
    """Rule-based mutation/evolution of architectures (deterministic by default).

    When `use_llm=True` external LLM calls could be used; in the default
    deterministic mode, mutations are driven by rule-based patterns informed by
    the candidate's weakest objectives and stored experience.
    """

    def __init__(
        self,
        use_llm: bool = False,
        mutation_count: int = 2,
        seed: Optional[int] = None,
    ):
        self.use_llm = use_llm
        self.mutation_count = mutation_count
        self.rng = random.Random(seed if seed is not None else 42)

        self.mutation_patterns = self._init_mutation_patterns()

    def _init_mutation_patterns(self) -> Dict[str, Any]:
        """Initialize predefined mutation patterns for deterministic mode."""
        return {
            "add_cache": {
                "description": "Add a Redis cache layer",
                "target_objectives": ["performance", "scalability"],
                "apply": self._mutate_add_cache,
            },
            "remove_service": {
                "description": "Consolidate services to reduce cost",
                "target_objectives": ["cost"],
                "apply": self._mutate_remove_service,
            },
            "add_messaging": {
                "description": "Add a message broker for decoupling",
                "target_objectives": ["reliability", "scalability"],
                "apply": self._mutate_add_messaging,
            },
            "managed_to_unmanaged": {
                "description": "Switch managed services to self-hosted",
                "target_objectives": ["cost"],
                "apply": self._mutate_managed_to_unmanaged,
            },
            "add_gateway": {
                "description": "Add an API gateway for security",
                "target_objectives": ["security"],
                "apply": self._mutate_add_gateway,
            },
            "add_replication": {
                "description": "Add service and database replication",
                "target_objectives": ["reliability", "performance"],
                "apply": self._mutate_add_replication,
            },
            "add_security_layer": {
                "description": "Add a security layer (WAF / secrets vault)",
                "target_objectives": ["security"],
                "apply": self._mutate_add_security_layer,
            },
        }

    def mutate(
        self,
        candidate: Candidate,
        requirements: str,
        experience_memory: Optional["JsonExperienceMemory"] = None,
        application_type: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[MutationResult]:
        """Produce mutated architectures from a selected candidate.

        Args:
            candidate: The selected candidate to mutate
            requirements: Original requirement text
            experience_memory: Optional experience memory for context
            application_type: Application/system type for domain-aware mutation
            constraints: Optional structured constraints

        Returns:
            List of MutationResult objects
        """
        from ..requirements import parse_requirement
        parsed = parse_requirement(requirements)

        weaknesses = self._identify_weaknesses(candidate)

        experience_context: Dict[str, Any] = {}
        experience_used: List[str] = []
        if experience_memory:
            entries = experience_memory.recent_entries(
                min_score=max(candidate.overall_fitness, 0),
                limit=3,
            )
            if entries:
                experience_used = [str(e) for e in entries]
                experience_context = {
                    "previous_experiences": experience_used,
                    "requirement_context": parsed.raw_input,
                }

        domain_context = {"application_type": application_type, "constraints": constraints or {}}

        target_objectives = self._prioritize_weaknesses(candidate, experience_context)

        results: List[MutationResult] = []
        applied_patterns: Set[str] = set()

        while len(results) < self.mutation_count and self.mutation_patterns:
            pattern_name = self._select_mutation_pattern(
                target_objectives, applied_patterns, domain_context
            )
            if pattern_name not in self.mutation_patterns:
                break

            pattern = self.mutation_patterns[pattern_name]
            applied_patterns.add(pattern_name)

            new_arch = pattern["apply"](
                candidate.architecture, parsed, experience_context, domain_context
            )

            engine = FitnessEngine()
            fitness_result = engine.evaluate_and_score(new_arch, candidate.generation + 1)

            modifications = self._generate_modifications(
                pattern, candidate, fitness_result
            )
            reasoning = self._generate_reasoning(
                pattern, candidate, fitness_result, weaknesses
            )

            results.append(
                MutationResult(
                    new_architecture=new_arch,
                    modifications=modifications,
                    reasoning=reasoning,
                    source_weaknesses=weaknesses,
                    experience_used=experience_used,
                )
            )

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
        sorted_objectives = sorted(scores.items(), key=lambda x: x[1])

        for obj_name, score in sorted_objectives[:2]:
            if score < 70:
                weaknesses.append(f"low {obj_name} ({score:.1f})")

        if not weaknesses:
            weaknesses = ["no significant weaknesses identified"]

        return weaknesses

    def _prioritize_weaknesses(
        self, candidate: Candidate, experience_context: Dict[str, Any]
    ) -> List[str]:
        """Prioritize mutation targets based on weaknesses."""
        scores = {
            "cost": candidate.cost,
            "security": candidate.security,
            "reliability": candidate.reliability,
            "performance": candidate.performance,
            "scalability": candidate.scalability,
        }
        prioritized = sorted(scores.items(), key=lambda x: x[1])
        return [obj_name for obj_name, _ in prioritized]

    def _select_mutation_pattern(
        self,
        target_objectives: List[str],
        applied: Set[str],
        domain_context: Dict[str, Any],
    ) -> Optional[str]:
        """Select a mutation pattern targeting the given objectives."""
        objective = target_objectives[0] if target_objectives else None

        objective_to_patterns = {
            "cost": ["remove_service", "managed_to_unmanaged"],
            "security": ["add_gateway", "add_security_layer"],
            "reliability": ["add_messaging", "add_replication"],
            "performance": ["add_cache", "add_replication"],
            "scalability": ["add_messaging", "add_cache"],
        }

        relevant_patterns = objective_to_patterns.get(objective, [])
        available = [p for p in relevant_patterns if p not in applied]

        if not available:
            all_unapplied = [
                p for p in self.mutation_patterns.keys() if p not in applied
            ]
            return all_unapplied[0] if all_unapplied else None

        return available[0]

    # --- Concrete mutation application methods ---

    def _clone_architecture(self, architecture: Architecture, name: str = None) -> Architecture:
        comps = [c.model_copy(deep=True) for c in architecture.components]
        return Architecture(
            name=name or architecture.name,
            generation=architecture.generation + 1,
            components=comps,
            services=list(architecture.services),
            deployment_strategy=architecture.deployment_strategy,
            communication_pattern=architecture.communication_pattern,
            design_rationale=architecture.design_rationale,
            assumptions=list(architecture.assumptions),
            description=architecture.description,
        )

    def _mutate_add_cache(
        self,
        architecture: Architecture,
        parsed: Any,
        context: Dict[str, Any],
        domain_context: Dict[str, Any] = None,
    ) -> Architecture:
        new_arch = self._clone_architecture(architecture)
        if not any(c.type == "cache" for c in new_arch.components):
            new_arch.components.append(Component(name="Redis", type="cache", managed=True))
        else:
            for c in new_arch.components:
                if c.type == "cache":
                    c.managed = True
                    c.properties["enabled"] = True
        new_arch.name = f"{architecture.name} with Cache"
        return new_arch

    def _mutate_remove_service(
        self,
        architecture: Architecture,
        parsed: Any,
        context: Dict[str, Any],
        domain_context: Dict[str, Any] = None,
    ) -> Architecture:
        new_arch = self._clone_architecture(architecture)
        service_comps = [c for c in new_arch.components if c.type == "service"]
        if service_comps:
            to_remove = self.rng.choice(service_comps)
            new_arch.components = [
                c for c in new_arch.components if c.name != to_remove.name
            ]
        new_arch.name = f"{architecture.name} (Consolidated)"
        return new_arch

    def _mutate_add_messaging(
        self,
        architecture: Architecture,
        parsed: Any,
        context: Dict[str, Any],
        domain_context: Dict[str, Any] = None,
    ) -> Architecture:
        new_arch = self._clone_architecture(architecture)
        if not any(c.type == "messaging" for c in new_arch.components):
            new_arch.components.append(
                Component(name="RabbitMQ", type="messaging", managed=False)
            )
        new_arch.communication_pattern = "event-driven"
        new_arch.name = f"{architecture.name} with Messaging"
        return new_arch

    def _mutate_managed_to_unmanaged(
        self,
        architecture: Architecture,
        parsed: Any,
        context: Dict[str, Any],
        domain_context: Dict[str, Any] = None,
    ) -> Architecture:
        new_arch = self._clone_architecture(architecture)
        for c in new_arch.components:
            if c.managed and c.type not in ("gateway", "database", "security"):
                c.managed = False
        new_arch.name = f"{architecture.name} (Unmanaged)"
        return new_arch

    def _mutate_add_gateway(
        self,
        architecture: Architecture,
        parsed: Any,
        context: Dict[str, Any],
        domain_context: Dict[str, Any] = None,
    ) -> Architecture:
        new_arch = self._clone_architecture(architecture)
        if not any(c.type == "gateway" for c in new_arch.components):
            new_arch.components.append(
                Component(name="API Gateway", type="gateway", managed=True)
            )
        new_arch.name = f"{architecture.name} with Gateway"
        return new_arch

    def _mutate_add_replication(
        self,
        architecture: Architecture,
        parsed: Any,
        context: Dict[str, Any],
        domain_context: Dict[str, Any] = None,
    ) -> Architecture:
        new_arch = self._clone_architecture(architecture)
        for c in new_arch.components:
            if c.type == "database" and c.quantity < 3:
                c.quantity = 3  # primary + read replicas
                c.properties["replication"] = "primary-replica"
            if c.type == "service" and c.quantity < 3:
                c.quantity = 3
                c.properties["replicas"] = 3
        new_arch.name = f"{architecture.name} (Replicated)"
        return new_arch

    def _mutate_add_security_layer(
        self,
        architecture: Architecture,
        parsed: Any,
        context: Dict[str, Any],
        domain_context: Dict[str, Any] = None,
    ) -> Architecture:
        new_arch = self._clone_architecture(architecture)
        if not any(c.type == "security" for c in new_arch.components):
            name = "Secrets Vault"
            if domain_context and domain_context.get("constraints", {}).get("compliance"):
                name = "Encryption & Secrets Vault"
            new_arch.components.append(Component(name=name, type="security", managed=True))
        new_arch.name = f"{architecture.name} (Hardened)"
        return new_arch

    def _generate_modifications(
        self, pattern: Any, candidate: Candidate, fitness_result: Any
    ) -> List[str]:
        """Generate human-readable modification descriptions."""
        description = (
            pattern["description"] if isinstance(pattern, dict) else pattern["description"]
        )
        return [
            description,
            f"Fitness improved {candidate.overall_fitness:.1f} -> {fitness_result.overall_fitness:.1f}",
        ]

    def _generate_reasoning(
        self,
        pattern: Any,
        candidate: Candidate,
        fitness_result: Any,
        weaknesses: List[str],
    ) -> str:
        """Generate reasoning for the mutation."""
        target = (
            pattern["target_objectives"][0] if isinstance(pattern, dict) else pattern["target_objectives"][0]
        )
        reason_parts = [
            f"Targeted weak {target} objective.",
            f"Fitness {candidate.overall_fitness:.1f} -> {fitness_result.overall_fitness:.1f}.",
        ]
        if weaknesses:
            safe = [w for w in weaknesses if w != "no significant weaknesses identified"]
            if safe:
                reason_parts.append("Weaknesses: " + ", ".join(safe) + ".")
        return " ".join(reason_parts)