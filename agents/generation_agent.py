from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .base import BaseAgent, AgentTraceEntry, LLMClient
from .requirement_agent import StructuredRequirements
from ..models.architecture import Architecture
from ..generation.architecture_generator import ArchitectureGenerator


class ArchitectureGenerationAgent(BaseAgent):
    """Agent responsible for generating diverse candidate system architectures based on requirements.

    Defined Input:
        - requirements: StructuredRequirements produced by RequirementAnalysisAgent.
        - population_size: Number of initial candidate architectures to generate.
        - seed: Deterministic random seed.

    Defined Output:
        - List of candidate Architecture models, each representing a meaningfully different topology
          (e.g., Modular Monolith, Microservices, Event-Driven, Serverless, Hybrid).
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(
            name="Architecture Generation Agent",
            role="Synthesizes diverse, domain-specialized candidate architectures matching structured requirements",
            llm_client=llm_client,
        )

    def run(
        self,
        requirements: StructuredRequirements,
        population_size: int = 5,
        seed: int = 42,
    ) -> Tuple[List[Architecture], List[AgentTraceEntry]]:
        """Generate candidate architectures."""
        generator = ArchitectureGenerator(
            population_size=population_size,
            seed=seed,
            application_type=requirements.application_type,
            constraints=requirements.constraints,
        )

        candidates = generator.generate_initial_population(
            raw_requirement=requirements.raw_input,
            application_type=requirements.application_type,
            constraints=requirements.constraints,
        )

        traces: List[AgentTraceEntry] = []
        for i, arch in enumerate(candidates):
            comp_types = [c.type for c in arch.components]
            trace = AgentTraceEntry(
                agent=self.name,
                action="Generate Candidate",
                architecture=arch.name,
                reason=f"Synthesized {arch.deployment_strategy} architecture using {arch.communication_pattern} communication pattern ({len(arch.components)} components).",
                outcome="generated",
                generation=0,
                details={
                    "candidate_index": i + 1,
                    "communication_pattern": arch.communication_pattern,
                    "deployment_strategy": arch.deployment_strategy,
                    "components": [c.name for c in arch.components],
                },
            )
            traces.append(trace)

        return candidates, traces
