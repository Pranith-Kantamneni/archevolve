from __future__ import annotations

import random
from typing import List, Dict, Any, Optional

from ..models.architecture import (
    Architecture,
    Component,
    ArchitectureModel,
    domain_extra_components_for,
    domain_services_for,
)
from ..requirements import parse_requirement


class ArchitectureGenerator:
    """Generates initial candidate architectures from parsed requirements.

    Candidates are influenced by the application type (domain services and
    components) and the parsed requirements, so different systems produce
    different initial populations.
    """

    # Templates for different architectural styles
    TEMPLATES = [
        ArchitectureModel.create_monolith,
        ArchitectureModel.create_microservices,
        ArchitectureModel.create_serverless,
        ArchitectureModel.create_event_driven,
        ArchitectureModel.create_hybrid,
    ]

    def __init__(
        self,
        population_size: int = 5,
        seed: int = 42,
        application_type: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ):
        self.population_size = population_size
        self.seed = seed
        self.application_type = application_type
        self.constraints = constraints or {}
        self.rng = random.Random(seed)

    def generate_initial_population(
        self,
        raw_requirement: str,
        application_type: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[Architecture]:
        """Generate an initial population of diverse candidate architectures."""
        if application_type is not None:
            self.application_type = application_type
        if constraints is not None:
            self.constraints = constraints or {}
        parsed = parse_requirement(raw_requirement)
        return self._generate_population_from_parsed(parsed)

    def _generate_population_from_parsed(self, parsed: Any) -> List[Architecture]:
        """Generate architectures from a parsed requirement."""
        # Base context from parsed requirements + application domain
        context = self._build_architecture_context(parsed)

        candidates: List[Architecture] = []
        template_count = min(len(self.TEMPLATES), self.population_size)

        selected_templates = self.rng.sample(self.TEMPLATES, template_count)

        for i, template_fn in enumerate(selected_templates):
            architecture = template_fn(context)
            architecture.name = (
                f"{architecture.name} #{i + 1}"
                if len(candidates) > 0
                else architecture.name
            )
            architecture.generation = 0
            candidates.append(architecture)

        # Fill remaining slots with variations of existing templates
        while len(candidates) < self.population_size:
            template_fn = self.rng.choice(self.TEMPLATES)
            architecture = template_fn(context)
            architecture.generation = 0
            architecture = self._add_variation(architecture, context)
            architecture.name = f"{architecture.name} Variant"
            candidates.append(architecture)

        # Fallback: guaranteed app-aware candidate
        while len(candidates) < self.population_size:
            architecture = ArchitectureModel.create_hybrid(context)
            architecture.generation = 0
            architecture.name = "Custom Adaptation"
            candidates.append(architecture)

        return candidates

    def _build_architecture_context(self, parsed: Any) -> Dict[str, Any]:
        """Build a context dict from parsed requirements + application type."""
        app_type = self.application_type or ""
        context: Dict[str, Any] = {
            "application_type": app_type,
            "domain_services": domain_services_for(app_type),
            "domain_extras": domain_extra_components_for(app_type),
            "expected_users": parsed.expected_users or 1000,
            "max_latency_ms": parsed.max_latency_ms or 200,
            "availability_percentage": parsed.availability_percentage or 99.9,
            "security_level": parsed.security_level or "medium",
            "scalability_type": parsed.scalability_type or "horizontal",
            "cost_sensitive": parsed.cost_sensitive,
            "deployment_env": parsed.deployment_environment or "cloud",
            "preferred_technologies": parsed.preferred_technologies,
            "compliance_requirements": parsed.compliance_requirements,
            "max_monthly_cost": parsed.max_monthly_cost,
            "assumptions": self._derive_assumptions(parsed),
        }
        # Merge explicit constraints into the context
        context.update(self._constraints_context())
        return context

    def _constraints_context(self) -> Dict[str, Any]:
        """Turn user-provided constraints into architecture context hints."""
        hints: Dict[str, Any] = {}
        c = self.constraints or {}

        if c.get("provider"):
            hints["cloud_provider"] = c["provider"]
            tech = {
                "aws": ["AWS Lambda", "Amazon RDS"],
                "gcp": ["Cloud Functions", "Cloud SQL"],
                "azure": ["Azure Functions", "Azure SQL"],
            }
            matches = [t for k, t in tech.items() if k in str(c["provider"]).lower()]
            if matches:
                hints["preferred_components"] = matches[0]

        if c.get("max_budget"):
            hints["max_monthly_cost"] = c["max_budget"]

        if c.get("technologies"):
            hints["preferred_components"] = list(c["technologies"])

        if c.get("database"):
            hints["database_preference"] = c["database"]

        if c.get("compliance"):
            hints["compliance_requirements"] = list(c["compliance"])

        if c.get("deployment"):
            hints["deployment_env"] = c["deployment"]
        return hints

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
        if self.application_type:
            assumptions.append(f"{self.application_type} domain")
        if not assumptions:
            assumptions = ["Standard deployment assumptions"]
        return assumptions

    def _add_variation(
        self, architecture: Architecture, context: Dict[str, Any]
    ) -> Architecture:
        """Add deliberate variation to an architecture candidate."""
        comps = list(architecture.components)

        # Add messaging for async-capable styles if missing
        if context["scalability_type"] == "horizontal" and not any(
            c.type == "messaging" for c in comps
        ):
            comps.append(Component(name="RabbitMQ", type="messaging", managed=False))

        if context["cost_sensitive"]:
            for c in comps:
                if c.managed and c.type not in ("gateway", "database", "security"):
                    c.managed = False

        architecture.components = comps
        return architecture