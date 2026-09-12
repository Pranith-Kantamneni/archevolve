from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator


class Component(BaseModel):
    """A structured architectural component."""

    name: str = Field(description="Component name (e.g., 'PostgreSQL', 'Redis')")
    type: str = Field(description="Component type (e.g., 'database', 'cache', 'messaging')")
    quantity: int = Field(
        default=1, ge=1, description="Number of instances"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Component-specific properties"
    )
    managed: bool = Field(
        default=False, description="Whether the component is a managed service"
    )

    def __str__(self) -> str:
        if self.quantity > 1:
            return f"{self.name} ({self.quantity} instances)"
        return self.name


class Architecture(BaseModel):
    """Structured representation of a software architecture."""

    name: str = Field(description="Architecture name/identifier")
    generation: int = Field(
        default=0, ge=0, description="Generation number in evolutionary process"
    )

    # Core architectural decisions
    components: List[Component] = Field(
        default_factory=list, description="Architectural components"
    )
    services: List[str] = Field(
        default_factory=list, description="Service names"
    )
    deployment_strategy: str = Field(
        default="standard",
        description="Deployment strategy (e.g., 'standard', 'blue-green', 'canary')",
    )
    communication_pattern: str = Field(
        default="sync",
        description="Primary communication pattern (e.g., 'sync', 'async', 'event-driven')",
    )

    # Derived/estimated fields
    estimated_resource_requirements: Dict[str, Any] = Field(
        default_factory=dict, description="Estimated compute, storage, network requirements"
    )
    design_rationale: str = Field(
        default="", description="Human-readable design rationale"
    )
    assumptions: List[str] = Field(
        default_factory=list, description="Key assumptions underlying this architecture"
    )

    # Human-readable description
    description: str = Field(
        default="", description="Human-readable architecture description"
    )

    class Config:
        arbitrary_types_allowed = True

    def __str__(self) -> str:
        comp_names = ", ".join(c.name for c in self.components)
        return f"{self.name} [{comp_names}] gen-{self.generation}"


class ArchitectureModel:
    """Utility class for architecture creation and manipulation."""

    @staticmethod
    def create_monolith(requirement_context: Dict[str, Any]) -> Architecture:
        """Create a modular monolith architecture."""
        comps = [
            Component(name="API Gateway", type="gateway", managed=True),
            Component(name="Application Layer", type="application", quantity=1),
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis Cache", type="cache", managed=True),
        ]
        return Architecture(
            name="Modular Monolith",
            generation=0,
            components=comps,
            deployment_strategy="standard",
            communication_pattern="sync",
            design_rationale="Single deployable unit with centralized database and cache. Simple to operate but may limit scalability.",
            assumptions=list(requirement_context.get("assumptions", ["Single team", "Moderate traffic"])),
        )

    @staticmethod
    def create_microservices(requirement_context: Dict[str, Any]) -> Architecture:
        """Create a microservices architecture."""
        comps = [
            Component(name="API Gateway", type="gateway", managed=True),
            Component(name="Auth Service", type="service", quantity=1),
            Component(name="Order Service", type="service", quantity=1),
            Component(name="Product Service", type="service", quantity=1),
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis", type="cache", managed=True),
            Component(name="RabbitMQ", type="messaging", managed=False),
        ]
        return Architecture(
            name="Microservices",
            generation=0,
            components=comps,
            services=["auth", "order", "product"],
            deployment_strategy="containerized",
            communication_pattern="async",
            design_rationale="Loosely coupled services enable independent scaling and deployment. Introduces operational complexity but improves fault isolation.",
            assumptions=list(requirement_context.get("assumptions", ["Multiple teams", "High traffic"])),
        )

    @staticmethod
    def create_serverless(requirement_context: Dict[str, Any]) -> Architecture:
        """Create a serverless architecture."""
        comps = [
            Component(name="API Gateway", type="gateway", managed=True),
            Component(name="Function Compute", type="compute", managed=True),
            Component(name="Managed Database", type="database", managed=True),
            Component(name="Managed Cache", type="cache", managed=True),
        ]
        return Architecture(
            name="Serverless",
            generation=0,
            components=comps,
            deployment_strategy="serverless",
            communication_pattern="sync",
            design_rationale="No server management required; auto-scaling and pay-per-use. cold start latency and vendor lock-in are trade-offs.",
            assumptions=list(requirement_context.get("assumptions", ["Event-driven workload", "Variable traffic"])),
        )

    @staticmethod
    def create_event_driven(requirement_context: Dict[str, Any]) -> Architecture:
        """Create an event-driven architecture."""
        comps = [
            Component(name="API Gateway", type="gateway", managed=True),
            Component(name="Event Bus", type="messaging", managed=False),
            Component(name="Order Service", type="service", quantity=1),
            Component(name="Product Service", type="service", quantity=1),
            Component(name="Auth Service", type="service", quantity=1),
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis", type="cache", managed=True),
        ]
        return Architecture(
            name="Event-Driven",
            generation=0,
            components=comps,
            services=["order", "product", "auth"],
            deployment_strategy="containerized",
            communication_pattern="event-driven",
            design_rationale="Event-driven communication enables high decoupling and scalability. Requires robust event handling and monitoring.",
            assumptions=list(requirement_context.get("assumptions", ["High throughput", "Event-capable team"])),
        )