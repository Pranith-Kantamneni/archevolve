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

        # Choose templates with bias based on workload size
        selected_templates = self._select_templates(context, template_count)

        for i, template_fn in enumerate(selected_templates):
            architecture = template_fn(context)
            # Apply workload-driven adjustments before naming
            architecture = self._apply_workload_scaling(architecture, context)
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
            # Apply workload-driven adjustments for variant candidates as well
            architecture = self._apply_workload_scaling(architecture, context)
            architecture.name = f"{architecture.name} Variant"
            candidates.append(architecture)

        # Fallback: guaranteed app-aware candidate
        while len(candidates) < self.population_size:
            architecture = ArchitectureModel.create_hybrid(context)
            architecture.generation = 0
            architecture.name = "Custom Adaptation"
            # Ensure even fallback candidates respect workload scaling
            architecture = self._apply_workload_scaling(architecture, context)
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
        if parsed.expected_users and parsed.expected_users > 1000000:
            assumptions.append("Very high traffic (>=1M users)")
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

        if context.get("cost_sensitive"):
            for c in comps:
                if c.managed and c.type not in ("gateway", "database", "security"):
                    c.managed = False

        architecture.components = comps
        return architecture

    def _apply_workload_scaling(self, architecture: Architecture, context: Dict[str, Any]) -> Architecture:
        """Adjust architecture components based on workload signals.

        Modifies components such as load balancers, DB replicas, cache clusters, and CDN
        according to expected users, latency requirements, and cost sensitivity.
        Reasons are recorded in each component's ``properties`` for traceability.
        """
        comps = list(architecture.components)
        expected = context.get("expected_users", 0)
        latency = context.get("max_latency_ms")
        cost_sensitive = context.get("cost_sensitive", False)

        # High traffic (>=1M users) – add load balancer and scale DB replicas
        if expected >= 1_000_000:
            if not any(c.type == "gateway" and "Load Balancer" in c.name for c in comps):
                comps.append(
                    Component(
                        name="Load Balancer",
                        type="gateway",
                        managed=True,
                        properties={"reason": "Very high expected users require traffic distribution"},
                    )
                )
            for c in comps:
                if c.type == "database" and c.quantity < 2:
                    c.quantity = 2
                    c.properties = {**(c.properties or {}), "reason": "Add replica for high‑traffic resilience"}
        # Moderate‑high traffic (>=100k users) – ensure cache and DB replica
        elif expected >= 100_000:
            if not any(c.type == "cache" for c in comps):
                comps.append(
                    Component(
                        name="Redis Cache",
                        type="cache",
                        managed=True,
                        properties={"reason": "Cache to reduce DB load for many users"},
                    )
                )
            for c in comps:
                if c.type == "database" and c.quantity < 2:
                    c.quantity = 2
                    c.properties = {**(c.properties or {}), "reason": "Second DB instance for increased load"}
        # Low latency requirement (<=100ms) – add edge CDN
        if latency is not None and latency <= 100:
            if not any(c.type == "cdn" for c in comps):
                comps.append(
                    Component(
                        name="Edge CDN",
                        type="cdn",
                        managed=True,
                        properties={"reason": "Sub‑100ms latency SLA requires edge caching"},
                    )
                )
        # Cost‑sensitive mode – downgrade non‑essential managed services
        if cost_sensitive:
            for c in comps:
                if c.managed and c.type not in ("gateway", "database", "security"):
                    c.managed = False
                    c.properties = {**(c.properties or {}), "reason": "Cost‑sensitive – prefer self‑managed component"}
        architecture.components = comps
        return architecture

    def _select_templates(self, context: Dict[str, Any], count: int) -> List[Any]:
        """Select architecture templates with workload‑aware bias.

        For very high traffic (>1M users) we prioritize microservices and hybrid styles
        to ensure scalability. For moderate traffic (>100k) we allow a mix but still
        include at least one microservices template. For low traffic we keep the full
        random selection.
        """
        expected = context.get("expected_users", 0)
        # Determine weighted pool
        weighted_templates = []
        if expected >= 1_000_000:
            # Strong bias towards microservices and hybrid
            weighted_templates = [self.TEMPLATES[1], self.TEMPLATES[4]] * 3 + self.TEMPLATES
        elif expected >= 100_000:
            # Ensure at least one microservices template
            weighted_templates = [self.TEMPLATES[1]] * 2 + self.TEMPLATES
        else:
            weighted_templates = self.TEMPLATES
        # Sample without replacement; if pool smaller than count, fallback to unique set
        unique_pool = list(dict.fromkeys(weighted_templates))
        if len(unique_pool) <= count:
            return unique_pool[:count]
        return self.rng.sample(unique_pool, count)