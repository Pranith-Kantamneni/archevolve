from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import BaseAgent, AgentTraceEntry, LLMClient
from .requirement_agent import StructuredRequirements
from ..models.architecture import Architecture, Component
from ..fitness.fitness_engine import Candidate
from ..memory.experience_memory import ExperienceEntry


class ArchitectureMutation:
    """Detailed record of a single architectural mutation operation."""

    def __init__(
        self,
        new_architecture: Architecture,
        what_changed: List[str],
        why_it_changed: str,
        weakness_addressed: str,
        triggering_agent: str,
        experience_used: List[str],
        parent_architecture_name: str,
        parent_fitness: float,
        child_fitness: Optional[float] = None,
        outcome: str = "pending",  # "improved" | "degraded" | "neutral"
        improvement_delta: float = 0.0,
    ):
        self.new_architecture = new_architecture
        self.what_changed = what_changed
        self.why_it_changed = why_it_changed
        self.weakness_addressed = weakness_addressed
        self.triggering_agent = triggering_agent
        self.experience_used = experience_used
        self.parent_architecture_name = parent_architecture_name
        self.parent_fitness = parent_fitness
        self.child_fitness = child_fitness
        self.outcome = outcome
        self.improvement_delta = improvement_delta

        # Backwards compatibility attributes
        self.modifications = what_changed
        self.reasoning = why_it_changed
        self.source_weaknesses = [weakness_addressed] if weakness_addressed else []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.new_architecture.name,
            "source_architecture": self.parent_architecture_name,
            "parent_fitness": round(self.parent_fitness, 2),
            "fitness": round(self.child_fitness, 2) if self.child_fitness is not None else None,
            "what_changed": self.what_changed,
            "modifications": self.what_changed,
            "why_it_changed": self.why_it_changed,
            "reasoning": self.why_it_changed,
            "weakness_addressed": self.weakness_addressed,
            "source_weaknesses": self.source_weaknesses,
            "triggering_agent": self.triggering_agent,
            "experience_used": self.experience_used,
            "outcome": self.outcome,
            "improvement_delta": round(self.improvement_delta, 2),
        }


class ArchitectureEvolutionAgent(BaseAgent):
    """Agent responsible for evolving candidate architectures by addressing specific weaknesses.

    Defined Input:
        - parent: Selected candidate Architecture with evaluation feedback.
        - requirements: Structured requirements.
        - experiences: Dictionary containing both relevant past successes and failures.

    Defined Output:
        - List of mutated architectures with complete mutation provenance.
    """

    def __init__(
        self,
        mutation_count: int = 2,
        seed: Optional[int] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        super().__init__(
            name="Architecture Evolution Agent",
            role="Applies targeted architectural mutations informed by evaluation agent feedback and dual success/failure memory",
            llm_client=llm_client,
        )
        self.mutation_count = mutation_count
        self.rng = random.Random(seed if seed is not None else 42)

    def run(
        self,
        parent: Candidate,
        requirements: StructuredRequirements,
        experiences: Optional[Dict[str, List[ExperienceEntry]]] = None,
        generation: int = 1,
    ) -> Tuple[List[ArchitectureMutation], List[AgentTraceEntry]]:
        """Evolve parent candidate into improved architectures."""
        exp_dict = experiences or {"successes": [], "failures": []}
        successes = exp_dict.get("successes", [])
        failures = exp_dict.get("failures", [])

        weaknesses, triggering_agents = self._identify_target_weaknesses(parent)
        mutations: List[ArchitectureMutation] = []
        traces: List[AgentTraceEntry] = []

        patterns = self._get_mutation_catalog()
        applied_keys: Set[str] = set()

        for target_obj, trig_agent, weakness_desc in zip(
            ["performance", "security", "reliability", "cost", "scalability"],
            ["Performance Agent", "Security Agent", "Reliability Agent", "Cost Agent", "Scalability Agent"],
            [
                "sub-optimal latency/throughput without caching",
                "missing perimeter authentication / security layer",
                "lack of node redundancy and decoupling",
                "high component hosting overhead",
                "synchronous inter-service bottlenecks",
            ],
        ):
            if len(mutations) >= self.mutation_count:
                break

            # Check if this objective needs improvement
            obj_score = getattr(parent, target_obj, 100)
            if obj_score >= 85 and len(mutations) > 0:
                continue  # Already strong

            # Pick suitable pattern
            candidate_patterns = [k for k, p in patterns.items() if p["target"] == target_obj and k not in applied_keys]
            if not candidate_patterns:
                continue

            # Consult memory: if any failure matches this pattern in this domain, avoid it
            selected_pattern_key = None
            for pkey in candidate_patterns:
                # Check if this pattern caused failure previously
                has_failed = any(
                    pkey.replace("_", " ") in f.reason.lower() or any(pkey.replace("_", " ") in m.lower() for m in f.modifications)
                    for f in failures
                )
                if not has_failed:
                    selected_pattern_key = pkey
                    break

            if not selected_pattern_key:
                selected_pattern_key = candidate_patterns[0]

            applied_keys.add(selected_pattern_key)
            pattern = patterns[selected_pattern_key]

            # Build experience notes
            exp_notes: List[str] = []
            for s in successes:
                if target_obj in s.reason.lower() or any(target_obj in w.lower() for w in s.weaknesses):
                    exp_notes.append(f"Reinforced by success: {s.reason}")
            for f in failures:
                if target_obj in f.reason.lower():
                    exp_notes.append(f"Cautioned by failure: {f.reason}")

            if not exp_notes and successes:
                exp_notes.append(f"Prior success reference: {successes[0].reason}")

            # Apply mutation function
            new_arch = pattern["apply"](parent.architecture, requirements)
            new_arch.generation = generation

            why_text = (
                f"Evaluation by {trig_agent} identified {weakness_desc} (score {obj_score:.1f}). "
                f"Applied {pattern['name']} to enhance {target_obj}."
            )
            if exp_notes:
                why_text += f" Informed by experience memory: {exp_notes[0]}"

            mutation = ArchitectureMutation(
                new_architecture=new_arch,
                what_changed=[pattern["description"]],
                why_it_changed=why_text,
                weakness_addressed=f"low {target_obj} ({obj_score:.1f})",
                triggering_agent=trig_agent,
                experience_used=exp_notes,
                parent_architecture_name=parent.architecture.name,
                parent_fitness=parent.overall_fitness,
            )
            mutations.append(mutation)

            trace = AgentTraceEntry(
                agent=self.name,
                action="Mutate Architecture",
                architecture=new_arch.name,
                reason=why_text,
                outcome="mutated",
                fitness=parent.overall_fitness,
                generation=generation,
                details={
                    "parent_architecture": parent.architecture.name,
                    "target_objective": target_obj,
                    "triggering_agent": trig_agent,
                    "modifications": mutation.what_changed,
                    "experience_consulted": exp_notes,
                },
            )
            traces.append(trace)

        # Fallback if no specific mutation matched
        if not mutations:
            pattern = patterns["add_cache"]
            new_arch = pattern["apply"](parent.architecture, requirements)
            new_arch.generation = generation
            mutation = ArchitectureMutation(
                new_architecture=new_arch,
                what_changed=[pattern["description"]],
                why_it_changed="Applied caching optimization to reinforce read throughput.",
                weakness_addressed="performance optimization",
                triggering_agent="Performance Agent",
                experience_used=[s.reason for s in successes[:1]],
                parent_architecture_name=parent.architecture.name,
                parent_fitness=parent.overall_fitness,
            )
            mutations.append(mutation)
            traces.append(
                AgentTraceEntry(
                    agent=self.name,
                    action="Mutate Architecture",
                    architecture=new_arch.name,
                    reason=mutation.why_it_changed,
                    outcome="mutated",
                    fitness=parent.overall_fitness,
                    generation=generation,
                    details={"modifications": mutation.what_changed},
                )
            )

        return mutations, traces

    def _identify_target_weaknesses(self, parent: Candidate) -> Tuple[List[str], List[str]]:
        scores = {
            "cost": ("Cost Agent", parent.cost),
            "security": ("Security Agent", parent.security),
            "reliability": ("Reliability Agent", parent.reliability),
            "performance": ("Performance Agent", parent.performance),
            "scalability": ("Scalability Agent", parent.scalability),
        }
        sorted_objs = sorted(scores.items(), key=lambda x: x[1][1])
        weaknesses = [f"{k} ({v[1]:.1f})" for k, v in sorted_objs if v[1] < 75]
        agents = [v[0] for k, v in sorted_objs if v[1] < 75]
        return weaknesses, agents

    def _clone_arch(self, arch: Architecture, suffix: str) -> Architecture:
        comps = [c.model_copy(deep=True) for c in arch.components]
        return Architecture(
            name=f"{arch.name} ({suffix})",
            generation=arch.generation + 1,
            components=comps,
            services=list(arch.services),
            deployment_strategy=arch.deployment_strategy,
            communication_pattern=arch.communication_pattern,
            design_rationale=arch.design_rationale,
            assumptions=list(arch.assumptions),
            description=arch.description,
        )

    def _get_mutation_catalog(self) -> Dict[str, Dict[str, Any]]:
        return {
            "add_cache": {
                "name": "In-Memory Cache Layer",
                "description": "Added Redis in-memory cache layer to reduce database read latency",
                "target": "performance",
                "apply": self._apply_add_cache,
            },
            "add_gateway": {
                "name": "API Gateway & Auth Boundary",
                "description": "Integrated managed API Gateway for centralized authentication, TLS termination, and traffic filtering",
                "target": "security",
                "apply": self._apply_add_gateway,
            },
            "add_messaging": {
                "name": "Asynchronous Message Queue",
                "description": "Introduced RabbitMQ/Kafka event streaming queue for decoupled service communication",
                "target": "reliability",
                "apply": self._apply_add_messaging,
            },
            "add_replication": {
                "name": "Multi-Instance Node Replication",
                "description": "Configured multi-instance service replication (3 replicas) for high availability and failover",
                "target": "reliability",
                "apply": self._apply_add_replication,
            },
            "add_security_vault": {
                "name": "Dedicated Secrets & Encryption Vault",
                "description": "Added Secrets & Encryption Vault component for automated cryptographic key management",
                "target": "security",
                "apply": self._apply_add_security_vault,
            },
            "consolidate_services": {
                "name": "Service Consolidation",
                "description": "Consolidated redundant microservices to reduce infrastructure footprint and operational cost",
                "target": "cost",
                "apply": self._apply_consolidate_services,
            },
        }

    def _apply_add_cache(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Cached")
        if not any(c.type == "cache" for c in new_arch.components):
            new_arch.components.append(Component(name="Redis Cache", type="cache", managed=True))
        else:
            for c in new_arch.components:
                if c.type == "cache":
                    c.managed = True
                    c.quantity = max(c.quantity, 2)
        return new_arch

    def _apply_add_gateway(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Gateway-Secured")
        if not any(c.type == "gateway" for c in new_arch.components):
            new_arch.components.insert(0, Component(name="API Gateway", type="gateway", managed=True))
        return new_arch

    def _apply_add_messaging(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Event-Driven")
        if not any(c.type == "messaging" for c in new_arch.components):
            new_arch.components.append(Component(name="RabbitMQ", type="messaging", managed=False))
        new_arch.communication_pattern = "event-driven"
        return new_arch

    def _apply_add_replication(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Replicated")
        for c in new_arch.components:
            if c.type in ("service", "application", "database"):
                c.quantity = max(c.quantity, 3)
                c.properties["replication"] = "active-active"
        return new_arch

    def _apply_add_security_vault(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Hardened")
        if not any(c.type == "security" for c in new_arch.components):
            name = "Secrets & Encryption Vault"
            if req.compliance_requirements:
                name = f"Compliance Vault ({', '.join(req.compliance_requirements)})"
            new_arch.components.append(Component(name=name, type="security", managed=True))
        return new_arch

    def _apply_consolidate_services(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Optimized")
        service_comps = [c for c in new_arch.components if c.type == "service"]
        if len(service_comps) > 3:
            # Consolidate one service
            to_remove = service_comps[-1]
            new_arch.components = [c for c in new_arch.components if c.name != to_remove.name]
        return new_arch
