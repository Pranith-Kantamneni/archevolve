from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


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

    def __str__(self) -> str:
        comp_names = ", ".join(c.name for c in self.components)
        return f"{self.name} [{comp_names}] gen-{self.generation}"


# ---------------------------------------------------------------------------
# Domain knowledge: map an application type to domain-specific service names
# and supporting components. This makes generated architectures respond to the
# user's application type instead of always returning e-commerce components.
# ---------------------------------------------------------------------------

APPLICATION_DOMAINS: Dict[str, Dict[str, Any]] = {
    "e-commerce": {
        "services": ["Product", "Order", "Cart", "Payment", "User", "Inventory"],
        "components": {
            "security": [],
            "data": [],
            "realtime": [],
        },
    },
    "food delivery": {
        "services": ["Restaurant", "Rider", "Order", "Payment", "User", "Notification"],
        "components": {
            "security": [],
            "data": [],
            "realtime": [],
        },
    },
    "banking": {
        "services": ["Account", "Transaction", "Ledger", "Audit", "User", "Fraud"],
        "components": {
            "security": ["WAF Firewall", "Secrets Vault", "Audit Logger", "KMS"],
            "data": [],
            "realtime": [],
        },
    },
    "finance": {
        "services": ["Account", "Transaction", "Ledger", "Audit", "User", "Fraud"],
        "components": {
            "security": ["WAF Firewall", "Secrets Vault", "Audit Logger", "KMS"],
            "data": [],
            "realtime": [],
        },
    },
    "healthcare": {
        "services": ["Patient", "Appointment", "Billing", "Records", "Provider", "User"],
        "components": {
            "security": ["WAF Firewall", "Secrets Vault", "Audit Logger", "KMS"],
            "data": [],
            "realtime": [],
        },
    },
    "chat": {
        "services": ["Message", "Presence", "Conversation", "User", "Notification"],
        "components": {
            "security": [],
            "data": ["Cassandra Message Store"],
            "realtime": ["WebSocket Hub", "Presence Cache"],
        },
    },
    "messaging": {
        "services": ["Message", "Presence", "Conversation", "User", "Notification"],
        "components": {
            "security": [],
            "data": ["Cassandra Message Store"],
            "realtime": ["WebSocket Hub", "Presence Cache"],
        },
    },
    "social media": {
        "services": ["Post", "Feed", "Follow", "Notification", "Media", "User"],
        "components": {
            "security": [],
            "data": ["Feed Cache", "Media Storage"],
            "realtime": [],
        },
    },
    "social": {
        "services": ["Post", "Feed", "Follow", "Notification", "Media", "User"],
        "components": {
            "security": [],
            "data": ["Feed Cache", "Media Storage"],
            "realtime": [],
        },
    },
    "learning": {
        "services": ["Course", "Enrollment", "Progress", "Video", "User", "Assessment"],
        "components": {
            "security": [],
            "data": ["Video Storage"],
            "realtime": [],
        },
    },
    "education": {
        "services": ["Course", "Enrollment", "Progress", "Video", "User", "Assessment"],
        "components": {
            "security": [],
            "data": ["Video Storage"],
            "realtime": [],
        },
    },
    "ride-sharing": {
        "services": ["Rider", "Driver", "Trip", "Dispatch", "Payment", "User"],
        "components": {
            "security": [],
            "data": ["Trip History Store"],
            "realtime": ["Location Ingestion Hub", "Dispatch Queue"],
        },
    },
    "ride sharing": {
        "services": ["Rider", "Driver", "Trip", "Dispatch", "Payment", "User"],
        "components": {
            "security": [],
            "data": ["Trip History Store"],
            "realtime": ["Location Ingestion Hub", "Dispatch Queue"],
        },
    },
    "streaming": {
        "services": ["Catalog", "Playback", "Recommendation", "Billing", "User"],
        "components": {
            "security": [],
            "data": ["Media CDN", "Video Storage"],
            "realtime": [],
        },
    },
    "video": {
        "services": ["Catalog", "Playback", "Recommendation", "Billing", "User"],
        "components": {
            "security": [],
            "data": ["Media CDN", "Video Storage"],
            "realtime": [],
        },
    },
    "iot": {
        "services": ["Device", "Ingestion", "Analytics", "Alerting", "User"],
        "components": {
            "security": ["Device Registry", "Secrets Vault"],
            "data": ["Time-Series Store"],
            "realtime": ["Device Ingestion Hub"],
        },
    },
    "gaming": {
        "services": ["Matchmaking", "Session", "Leaderboard", "Profile", "Inventory"],
        "components": {
            "security": [],
            "data": ["Game State Store"],
            "realtime": ["Realtime Gateway"],
        },
    },
}

# Generic services used when the application type is unknown.
GENERIC_SERVICES = ["Auth", "API", "Data", "User", "Notification"]


def detect_domain(application_type: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return domain knowledge for an application type, matched by keywords."""
    if not application_type:
        return None
    lowered = application_type.strip().lower()
    for key, domain in APPLICATION_DOMAINS.items():
        if key in lowered:
            return domain
    return None


def domain_services_for(application_type: Optional[str]) -> List[str]:
    """Return service names appropriate for the application type."""
    domain = detect_domain(application_type)
    if domain:
        return list(domain["services"])
    return list(GENERIC_SERVICES)


def domain_extra_components_for(application_type: Optional[str]) -> Dict[str, List[str]]:
    """Return supporting extra component names per category for the application type."""
    domain = detect_domain(application_type)
    if domain:
        return {
            "security": list(domain["components"].get("security", [])),
            "data": list(domain["components"].get("data", [])),
            "realtime": list(domain["components"].get("realtime", [])),
        }
    return {"security": [], "data": [], "realtime": []}


class ArchitectureModel:
    """Utility class for architecture creation and manipulation."""

    @staticmethod
    def _service_names(context: Dict[str, Any]) -> List[str]:
        """Resolve domain service names from the requirement context."""
        services = context.get("domain_services") or domain_services_for(
            context.get("application_type")
        )
        return list(services)

    @staticmethod
    def _extra_security_components(context: Dict[str, Any]) -> List[Component]:
        """Security stack derived from application domain and requirements."""
        extras = context.get("domain_extras", {}) or domain_extra_components_for(
            context.get("application_type")
        )
        comps = []
        for name in extras.get("security", []):
            comps.append(Component(name=name, type="security", managed=True))
        if context.get("security_level") == "high" and not any(
            c.type == "security" for c in comps
        ):
            comps.append(Component(name="WAF Firewall", type="security", managed=True))
            comps.append(Component(name="Secrets Vault", type="security", managed=True))
        return comps

    @staticmethod
    def _extra_data_components(context: Dict[str, Any]) -> List[Component]:
        """Domain-specific data stores."""
        extras = context.get("domain_extras", {}) or domain_extra_components_for(
            context.get("application_type")
        )
        return [
            Component(name=name, type="datastore", managed=True)
            for name in extras.get("data", [])
        ]

    @staticmethod
    def _extra_realtime_components(context: Dict[str, Any]) -> List[Component]:
        """Real-time / streaming infrastructure components."""
        extras = context.get("domain_extras", {}) or domain_extra_components_for(
            context.get("application_type")
        )
        comps = []
        for name in extras.get("realtime", []):
            if "Hub" in name or "Gateway" in name:
                comps.append(Component(name=name, type="realtime", managed=False))
            elif "Queue" in name or "Ingestion" in name:
                comps.append(Component(name=name, type="messaging", managed=False))
            else:
                comps.append(Component(name=name, type="realtime", managed=False))
        return comps

    @staticmethod
    def _entity_name(application_type: Optional[str]) -> str:
        """Pick a primary entity name used for the base service naming."""
        domain = detect_domain(application_type)
        if domain:
            return domain["services"][0]
        return "Core"

    @staticmethod
    def create_monolith(requirement_context: Dict[str, Any]) -> Architecture:
        """Create an application-aware modular monolith architecture."""
        context = requirement_context or {}
        services = ArchitectureModel._service_names(context)
        primary = services[0] if services else "Core"
        comps = [
            Component(name="API Gateway", type="gateway", managed=True),
            Component(name=f"{primary} Application Layer", type="application", quantity=1),
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis Cache", type="cache", managed=True),
        ]
        comps += ArchitectureModel._extra_security_components(context)
        comps += ArchitectureModel._extra_data_components(context)
        usage = context.get("expected_users", 1000)
        rationale = (
            f"Single deployable unit centered on {primary.lower()} workflows with a "
            f"centralized database and cache. Simple to operate and cost efficient for "
            f"{usage} expected users, but horizontal scaling is limited by monolith boundaries."
        )
        return Architecture(
            name="Modular Monolith",
            generation=0,
            components=comps,
            services=services,
            deployment_strategy="standard",
            communication_pattern="sync",
            design_rationale=rationale,
            assumptions=list(context.get("assumptions", ["Single team", "Moderate traffic"])),
        )

    @staticmethod
    def create_microservices(requirement_context: Dict[str, Any]) -> Architecture:
        """Create an application-aware microservices architecture."""
        context = requirement_context or {}
        services = ArchitectureModel._service_names(context)
        known_types = {"database", "cache", "gateway", "messaging", "security", "datastore", "realtime"}
        service_types = set(known_types)
        service_comps = [
            Component(name=f"{name} Service", type="service", quantity=1)
            for name in services
            if name.lower() not in {s.lower() for s in service_types}
        ]
        comps = [
            Component(name="API Gateway", type="gateway", managed=True),
        ]
        comps += service_comps
        comps += [
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis", type="cache", managed=True),
            Component(name="RabbitMQ", type="messaging", managed=False),
        ]
        comps += ArchitectureModel._extra_security_components(context)
        comps += ArchitectureModel._extra_data_components(context)
        comps += ArchitectureModel._extra_realtime_components(context)
        rationale = (
            f"Loosely coupled services ({', '.join(services)}) enable independent "
            f"scaling and deployment. Asynchronous messaging and caching improve "
            f"throughput and fault isolation at higher operational complexity."
        )
        return Architecture(
            name="Microservices",
            generation=0,
            components=comps,
            services=[s.lower() for s in services],
            deployment_strategy="containerized",
            communication_pattern="async",
            design_rationale=rationale,
            assumptions=list(context.get("assumptions", ["Multiple teams", "High traffic"])),
        )

    @staticmethod
    def create_serverless(requirement_context: Dict[str, Any]) -> Architecture:
        """Create an application-aware serverless architecture."""
        context = requirement_context or {}
        services = ArchitectureModel._service_names(context)
        comps = [
            Component(name="API Gateway", type="gateway", managed=True),
            Component(name="Function Compute", type="compute", managed=True),
            Component(name="Managed Database", type="database", managed=True),
            Component(name="Managed Cache", type="cache", managed=True),
        ]
        if context.get("scalability_type") == "horizontal" or context.get("expected_users", 0) > 10000:
            comps.append(Component(name="Event Queue", type="messaging", managed=True))
        comps += ArchitectureModel._extra_security_components(context)
        comps += ArchitectureModel._extra_data_components(context)
        comps += ArchitectureModel._extra_realtime_components(context)
        rationale = (
            f"Serverless functions around {', '.join(services[:3])} workflows with managed "
            f"data and cache layers. Auto-scales to zero during idle periods and pay-per-use "
            f"pricing; cold starts and vendor lock-in are trade-offs."
        )
        return Architecture(
            name="Serverless",
            generation=0,
            components=comps,
            services=[s.lower() for s in services],
            deployment_strategy="serverless",
            communication_pattern="sync",
            design_rationale=rationale,
            assumptions=list(context.get("assumptions", ["Event-driven workload", "Variable traffic"])),
        )

    @staticmethod
    def create_event_driven(requirement_context: Dict[str, Any]) -> Architecture:
        """Create an application-aware event-driven architecture."""
        context = requirement_context or {}
        services = ArchitectureModel._service_names(context)
        service_comps = [
            Component(name=f"{name} Service", type="service", quantity=1)
            for name in services
        ]
        comps = [
            Component(name="API Gateway", type="gateway", managed=True),
            Component(name="Event Bus", type="messaging", managed=False),
        ]
        comps += service_comps
        comps += [
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis", type="cache", managed=True),
        ]
        comps += ArchitectureModel._extra_security_components(context)
        comps += ArchitectureModel._extra_data_components(context)
        comps += ArchitectureModel._extra_realtime_components(context)
        rationale = (
            f"Event-driven processing where {', '.join(services[:4])} services publish and "
            f"consume domain events. Provides high decoupling, elastic scalability and "
            f"resilience; requires robust event handling and monitoring."
        )
        return Architecture(
            name="Event-Driven",
            generation=0,
            components=comps,
            services=[s.lower() for s in services],
            deployment_strategy="containerized",
            communication_pattern="event-driven",
            design_rationale=rationale,
            assumptions=list(context.get("assumptions", ["High throughput", "Event-capable team"])),
        )

    @staticmethod
    def create_hybrid(context: Dict[str, Any]) -> Architecture:
        """Create a hybrid architecture mixing microservices with serverless functions."""
        services = ArchitectureModel._service_names(context)
        service_comps = [
            Component(name=f"{name} Service", type="service", quantity=1)
            for name in services[:3]
        ]
        comps = [
            Component(name="API Gateway", type="gateway", managed=True),
        ]
        comps += service_comps
        comps += [
            Component(name="Function Compute", type="compute", managed=True),
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis", type="cache", managed=True),
            Component(name="RabbitMQ", type="messaging", managed=False),
        ]
        comps += ArchitectureModel._extra_security_components(context)
        comps += ArchitectureModel._extra_data_components(context)
        comps += ArchitectureModel._extra_realtime_components(context)
        return Architecture(
            name="Hybrid Architecture",
            generation=0,
            components=comps,
            services=[s.lower() for s in services],
            deployment_strategy="containerized",
            communication_pattern="async",
            design_rationale=(
                f"Hybrid design keeping {', '.join(services[:3])} as stable services while "
                f"offloading bursty workloads to serverless functions. Balances operational "
                f"control with elasticity."
            ),
            assumptions=list(context.get("assumptions", ["Mixed workload", "Multiple teams"])),
        )