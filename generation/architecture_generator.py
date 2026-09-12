from __future__ import annotations

import random
from typing import List, Dict, Any

from ..models.architecture import Architecture, Component, ArchitectureModel
from ..requirements import parse_requirement


class ArchitectureGenerator:
    """Generates initial candidate architectures from parsed requirements."""

    # Templates for different architectural styles
    TEMPLATES = [
        ArchitectureModel.create_monolith,
        ArchitectureModel.create_microservices,
        ArchitectureModel.create_serverless,
        ArchitectureModel.create_event_driven,
    ]

    def __init__(self, population_size: int = 5, seed: int = 42):
        self.population_size = population_size
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_initial_population(
        self, raw_requirement: str
    ) -> List[Architecture]:
        """Generate an initial population of diverse candidate architectures."""
        parsed = parse_requirement(raw_requirement)
        return self._generate_population_from_parsed(parsed)

    def _generate_population_from_parsed(self, parsed: ParsedRequirement) -> List[Architecture]:
        """Generate architectures from a parsed requirement."""
        # Base context from parsed requirements
        context = self._build_architecture_context(parsed)

        # Generate diverse architectures using different templates
        candidates = []
        template_count = min(
            len(self.TEMPLATES), self.population_size
        )

        # Select distinct templates
        selected_templates = self.rng.sample(
            self.TEMPLATES, template_count
        )

        for i, template_fn in enumerate(selected_templates):
            architecture = template_fn(context)
            architecture.name = (
                f"{architecture.name} #{i + 1}"
                if len(candidates) > 0
                else architecture.name
            )
            # Add a generation tag to differentiate
            architecture.generation = 0
            candidates.append(architecture)

        # Fill remaining slots with more variations
        while len(candidates) < self.population_size:
            # Pick a random template
            template_fn = self.rng.choice(self.TEMPLATES)
            architecture = template_fn(context)
            architecture.generation = 0
            # Ensure some uniqueness by modifying components
            architecture = self._add_variation(architecture, context)
            architecture.name = f"{architecture.name} Variant"
            candidates.append(architecture)

        # If we still have fewer than population_size, create a custom one
        while len(candidates) < self.population_size:
            architecture = ArchitectureModel.create_monolith(context)
            architecture.generation = 0
            architecture.name = "Custom Adaptation"
            candidates.append(architecture)

        return candidates

    def _build_architecture_context(self, parsed: Any) -> Dict[str, Any]:
        """Build a context dict from parsed requirements for architecture creation."""
        # Extract key info from parsed requirement
        context: Dict[str, Any] = {
            "expected_users": parsed.expected_users or 1000,
            "max_latency_ms": parsed.max_latency_ms or 200,
            "availability_percentage": parsed.availability_percentage or 99.9,
            "security_level": parsed.security_level or "medium",
            "scalability_type": parsed.scalability_type or "horizontal",
            "cost_sensitive": parsed.cost_sensitive,
            "deployment_env": parsed.deployment_environment or "cloud",
            "assumptions": self._derive_assumptions(parsed),
        }
        return context

    def _derive_assumptions(self, parsed: Any) -> List[str]:
        """Derive assumptions from parsed requirements."""
        assumptions = []
        if parsed.expected_users and parsed.expected_users > 10000:
            assumptions.append("High traffic volume")
        if parsed.cost_sensitive:
            assumptions.append("Cost optimization required")
        if parsed.security_level == "high":
            assumptions.append("Strong security requirements")
        if parsed.scalability_type == "horizontal":
            assumptions.append("Horizontal scaling needed")
        if not assumptions:
            assumptions = ["Standard deployment assumptions"]
        return assumptions

    def _add_variation(self, architecture: Architecture, context: Dict[str, Any]) -> Architecture:
        """Add deliberate variation to an architecture candidate."""
        # Randomly add/remove or modify components based on context
        comps = list(architecture.components)

        # Example variation: add messaging for non-microservices, add cache for read-heavy
        if context["scalability_type"] == "horizontal" and not any(
            c.type == "messaging" for c in comps
        ):
            comps.append(Component(name="RabbitMQ", type="messaging", managed=False))

        if context["cost_sensitive"]:
            # Replace managed with unmanaged where possible
            for c in comps:
                if c.managed and c.type != "gateway":
                    c.managed = False

        architecture.components = comps
        return architecture