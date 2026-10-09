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
        attempt: int = 0,
        focus: Optional[str] = None,
    ) -> Tuple[List[ArchitectureMutation], List[AgentTraceEntry]]:
        """Evolve parent candidate into improved architectures.

        Args:
            attempt: Retry attempt number. Rotates pattern choice so a retry
                produces *different* mutations instead of repeating attempt 0.
            focus: Optional dimension ('cost'|'security'|...) to target first.
        """
        exp_dict = experiences or {"successes": [], "failures": []}
        successes = exp_dict.get("successes", [])
        failures = exp_dict.get("failures", [])

        weaknesses, triggering_agents = self._identify_target_weaknesses(parent)
        mutations: List[ArchitectureMutation] = []
        traces: List[AgentTraceEntry] = []

        patterns = self._get_mutation_catalog()
        applied_keys: Set[str] = set()

        # 0. Domain pass: fix domain parameters first (they carry 20% of
        # fitness). Missing audit hubs, realtime hubs, CDNs, etc. are the
        # highest-leverage single-component additions.
        from ..evaluation.domain_params import PARAM_DEFS as _PARAM_DEFS

        parent_extras = getattr(parent, "extra_scores", {}) or {}
        for pkey in self._domain_opportunities(parent, requirements):
            if len(mutations) >= self.mutation_count:
                break
            if pkey not in patterns or pkey in applied_keys:
                continue
            applied_keys.add(pkey)
            pattern = patterns[pkey]
            exp_notes = self._experience_notes(successes, failures, pattern["target"], pattern["description"])
            label = _PARAM_DEFS.get(pkey, {}).get("label") or pattern["name"]
            dscore = parent_extras.get(pkey)
            desc = (f"low {label} ({dscore:.1f}/100)" if dscore is not None
                    else f"missing {label} capability for {requirements.application_type or 'this workload'}")
            mutations.append(self._build_mutation(
                parent, requirements, pattern, pkey, pattern["target"],
                desc, exp_notes, generation, obj_score=dscore,
            ))
            traces.append(self._mutation_trace(mutations[-1], parent, pattern, generation))

        targets = list(zip(
            ["performance", "security", "reliability", "cost", "scalability"],
            ["Performance Agent", "Security Agent", "Reliability Agent", "Cost Agent", "Scalability Agent"],
            [
                "sub-optimal latency/throughput without caching",
                "missing perimeter authentication / security layer",
                "lack of node redundancy and decoupling",
                "high component hosting overhead",
                "synchronous inter-service bottlenecks",
            ],
        ))
        if focus in {"cost", "security", "reliability", "performance", "scalability"}:
            targets.sort(key=lambda t: 0 if t[0] == focus else 1)

        for target_obj, trig_agent, weakness_desc in targets:
            if len(mutations) >= self.mutation_count:
                break

            # Check if this objective needs improvement
            obj_score = getattr(parent, target_obj, 100)
            if obj_score >= 85 and len(mutations) > 0:
                continue  # Already strong

            # Pick suitable pattern (rotated by attempt so retries vary)
            candidate_patterns = [k for k, p in patterns.items() if p["target"] == target_obj and k not in applied_keys]
            if not candidate_patterns:
                continue
            if attempt and len(candidate_patterns) > 1:
                rot = attempt % len(candidate_patterns)
                candidate_patterns = candidate_patterns[rot:] + candidate_patterns[:rot]

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
            exp_notes = self._experience_notes(successes, failures, target_obj, "")

            obj_score = getattr(parent, target_obj, 100)
            mutations.append(self._build_mutation(
                parent, requirements, pattern, selected_pattern_key,
                target_obj, weakness_desc, exp_notes, generation,
                trig_agent=trig_agent, obj_score=obj_score,
            ))
            traces.append(self._mutation_trace(mutations[-1], parent, pattern, generation))

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

        if attempt:
            for m in mutations:
                if f"(retry {attempt})" not in m.new_architecture.name:
                    m.new_architecture.name = f"{m.new_architecture.name} (retry {attempt})"

        return mutations, traces

    def _domain_opportunities(self, parent: Candidate, req: StructuredRequirements) -> List[str]:
        """Highest-leverage missing domain capabilities, as catalog keys."""
        from ..evaluation.domain_params import resolve_domain_params

        comps = parent.architecture.components
        types = {str(c.type).lower() for c in comps}
        names = " ".join(str(c.name).lower() for c in comps)
        params = resolve_domain_params(getattr(req, "application_type", "") or "")
        opps: List[str] = []
        comp_reqs = [r.lower() for r in (getattr(req, "compliance_requirements", []) or [])]
        auth_required = bool(getattr(req, "authentication_required", True))
        if "compliance_governance" in params or "data_privacy" in params:
            if "audit" not in names:
                opps.append("add_audit_logger")
            elif comp_reqs and not any(r in names for r in comp_reqs):
                opps.append("add_audit_logger")  # compliance-stamp upgrade path
            if "vault" not in names and "kms" not in names and "secrets" not in names:
                opps.append("add_security_vault")
        # Generic high-leverage gaps (any domain): dedicated identity is the
        # single biggest security lever (+15 identity) when absent.
        if auth_required and not any(
            k in names for k in ("auth", "identity", "cognito", "keycloak", "okta")
        ):
            opps.append("add_auth_service")
        if "transactional_consistency" in params:
            if "messaging" not in types:
                opps.append("add_messaging")
            if not any(str(c.type).lower() == "database" and int(c.quantity or 1) >= 2 for c in comps):
                opps.append("add_db_replica")
        if "realtime_delivery" in params:
            if "realtime" not in types and "websocket" not in names and "presence" not in names:
                opps.append("add_realtime_hub")
            if "messaging" not in types:
                opps.append("add_messaging")
        if "elastic_burst" in params:
            if "messaging" not in types:
                opps.append("add_messaging")
            if "cache" not in types:
                opps.append("add_cache")
        if "media_edge" in params:
            if "cdn" not in types and "edge" not in names:
                opps.append("add_cdn")
            if "datastore" not in types and "media" not in names and "video" not in names:
                opps.append("add_media_store")
        if "ingestion_scale" in params:
            if "messaging" not in types and "realtime" not in types:
                opps.append("add_messaging")
            if "datastore" not in types:
                opps.append("add_media_store")
        if "device_security" in params:
            if "registry" not in names and "auth" not in names:
                opps.append("add_gateway")
        # Generic high-leverage gaps (any domain)
        latency = getattr(req, "max_latency_ms", None)
        if latency is not None and float(latency) <= 100 and "cdn" not in types and "edge" not in names:
            opps.append("add_cdn")
        if str(getattr(parent.architecture, "deployment_strategy", "")).lower() == "standard" and (
            (getattr(req, "expected_users", 0) or 0) >= 100000
        ):
            opps.append("containerize")
        # De-duplicate, preserve order
        return list(dict.fromkeys(opps))

    @staticmethod
    def _experience_notes(successes: List[Any], failures: List[Any], target_obj: str, _hint: str = "") -> List[str]:
        exp_notes: List[str] = []
        for s in successes:
            if target_obj in s.reason.lower() or any(target_obj in w.lower() for w in s.weaknesses):
                exp_notes.append(f"Reinforced by success: {s.reason}")
        for f in failures:
            if target_obj in f.reason.lower():
                exp_notes.append(f"Cautioned by failure: {f.reason}")
        if not exp_notes and successes:
            exp_notes.append(f"Prior success reference: {successes[0].reason}")
        return exp_notes

    _TRIGGERS = {
        "performance": "Performance Agent", "security": "Security Agent",
        "reliability": "Reliability Agent", "cost": "Cost Agent",
        "scalability": "Scalability Agent",
    }

    def _build_mutation(self, parent: Candidate, req: StructuredRequirements, pattern: Dict[str, Any],
                        _pkey: str, target_obj: str, weakness_desc: str,
                        exp_notes: List[str], generation: int,
                        trig_agent: Optional[str] = None, obj_score: Optional[float] = None) -> ArchitectureMutation:
        new_arch = pattern["apply"](parent.architecture, req)
        new_arch.generation = generation
        trig = trig_agent or self._TRIGGERS.get(target_obj, "Architecture Evolution Agent")
        score = obj_score if obj_score is not None else getattr(parent, target_obj, 0.0)
        why_text = (
            f"Evaluation by {trig} identified {weakness_desc} (score {score:.1f}). "
            f"Applied {pattern['name']} to enhance {target_obj}."
        )
        if exp_notes:
            why_text += f" Informed by experience memory: {exp_notes[0]}"
        return ArchitectureMutation(
            new_architecture=new_arch,
            what_changed=[pattern["description"]],
            why_it_changed=why_text,
            weakness_addressed=f"low {target_obj} ({score:.1f})",
            triggering_agent=trig,
            experience_used=exp_notes,
            parent_architecture_name=parent.architecture.name,
            parent_fitness=parent.overall_fitness,
        )

    def _mutation_trace(self, mutation: ArchitectureMutation, parent: Candidate,
                        pattern: Dict[str, Any], generation: int) -> AgentTraceEntry:
        return AgentTraceEntry(
            agent=self.name,
            action="Mutate Architecture",
            architecture=mutation.new_architecture.name,
            reason=mutation.why_it_changed,
            outcome="mutated",
            fitness=parent.overall_fitness,
            generation=generation,
            details={
                "parent_architecture": parent.architecture.name,
                "target_objective": pattern.get("target", ""),
                "triggering_agent": mutation.triggering_agent,
                "modifications": mutation.what_changed,
                "experience_consulted": mutation.experience_used,
            },
        )

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
            "add_cdn": {
                "name": "Edge CDN",
                "description": "Added managed Edge CDN for sub-100ms static/media delivery",
                "target": "performance",
                "apply": self._apply_add_cdn,
            },
            "add_gateway": {
                "name": "API Gateway & Auth Boundary",
                "description": "Integrated managed API Gateway for centralized authentication, TLS termination, and traffic filtering",
                "target": "security",
                "apply": self._apply_add_gateway,
            },
            "add_waf": {
                "name": "WAF Firewall",
                "description": "Added WAF Firewall in front of the gateway for threat filtering",
                "target": "security",
                "apply": self._apply_add_waf,
            },
            "add_messaging": {
                "name": "Asynchronous Message Queue",
                "description": "Introduced RabbitMQ/Kafka event streaming queue for decoupled service communication",
                "target": "reliability",
                "apply": self._apply_add_messaging,
            },
            "add_db_replica": {
                "name": "Database Read Replica",
                "description": "Added a database read replica (×2) for failover and read scaling",
                "target": "reliability",
                "apply": self._apply_add_db_replica,
            },
            "smart_replication": {
                "name": "Smart Dual-Instance Replication",
                "description": "Scaled key service/database tiers to dual instances (×2) for failover without tripling cost",
                "target": "reliability",
                "apply": self._apply_smart_replication,
            },
            "add_lb": {
                "name": "Load Balancer",
                "description": "Added managed Load Balancer for health-checked traffic distribution",
                "target": "scalability",
                "apply": self._apply_add_lb,
            },
            "containerize": {
                "name": "Containerized Deployment",
                "description": "Migrated deployment to containerized substrate for independent auto-scaling",
                "target": "scalability",
                "apply": self._apply_containerize,
            },
            "add_realtime_hub": {
                "name": "Realtime Push Hub",
                "description": "Added WebSocket presence/push hub for sub-second live delivery",
                "target": "performance",
                "apply": self._apply_add_realtime_hub,
            },
            "add_media_store": {
                "name": "Dedicated Object Store",
                "description": "Added dedicated media/telemetry object store to offload the transactional database",
                "target": "scalability",
                "apply": self._apply_add_media_store,
            },
            "add_security_vault": {
                "name": "Dedicated Secrets & Encryption Vault",
                "description": "Added Secrets & Encryption Vault component for automated cryptographic key management",
                "target": "security",
                "apply": self._apply_add_security_vault,
            },
            "add_audit_logger": {
                "name": "Audit Logger",
                "description": "Added tamper-evident Audit Logger for compliance trails",
                "target": "security",
                "apply": self._apply_add_audit_logger,
            },
            "add_auth_service": {
                "name": "Dedicated Auth Service",
                "description": "Added dedicated Auth Service for centralized identity enforcement",
                "target": "security",
                "apply": self._apply_add_auth_service,
            },
            "consolidate_services": {
                "name": "Service Consolidation",
                "description": "Consolidated redundant microservices to reduce infrastructure footprint and operational cost",
                "target": "cost",
                "apply": self._apply_consolidate_services,
            },
            "cost_guard": {
                "name": "Managed-Premium Guard",
                "description": "Downgraded non-critical managed services to self-hosted to recover cost efficiency",
                "target": "cost",
                "apply": self._apply_cost_guard,
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
        elif not any(c.type == "security" for c in new_arch.components):
            # Gateway already exists: deepen the boundary with a WAF instead
            # of a no-op duplicate gateway.
            new_arch.components.insert(1, Component(name="WAF Firewall", type="security", managed=True))
            new_arch.name = new_arch.name.replace("Gateway-Secured", "WAF-Shielded")
        return new_arch

    def _apply_add_waf(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "WAF-Shielded")
        if not any("waf" in c.name.lower() or "firewall" in c.name.lower() for c in new_arch.components):
            idx = next((i for i, c in enumerate(new_arch.components) if c.type == "gateway"), 0)
            new_arch.components.insert(idx + 1 if new_arch.components else 0,
                                       Component(name="WAF Firewall", type="security", managed=True))
        return new_arch

    def _apply_add_cdn(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Edge-Accelerated")
        if not any(c.type == "cdn" for c in new_arch.components):
            new_arch.components.append(Component(name="Edge CDN", type="cdn", managed=True))
        return new_arch

    def _apply_add_lb(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Load-Balanced")
        if not any("load balancer" in c.name.lower() for c in new_arch.components):
            new_arch.components.insert(1 if len(new_arch.components) > 1 else 0,
                                       Component(name="Load Balancer", type="gateway", managed=True))
        return new_arch

    def _apply_add_db_replica(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Replica-Scaled")
        dbs = [c for c in new_arch.components if c.type == "database"]
        if dbs:
            primary = max(dbs, key=lambda c: c.quantity)
            primary.quantity = max(int(primary.quantity or 1), 2)
            primary.properties = {**(primary.properties or {}), "reason": "Read replica for failover and read scaling"}
        else:
            new_arch.components.append(Component(name="PostgreSQL Replica", type="database", managed=True, quantity=2))
        return new_arch

    def _apply_add_realtime_hub(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Realtime")
        if not any(c.type == "realtime" for c in new_arch.components):
            new_arch.components.append(Component(name="WebSocket Presence Hub", type="realtime", managed=False))
        if not any(c.type == "cache" for c in new_arch.components):
            new_arch.components.append(Component(name="Presence Cache", type="cache", managed=True))
        return new_arch

    def _apply_add_media_store(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Store-Offloaded")
        app = (getattr(req, "application_type", "") or "").lower()
        name = "Media Object Store" if any(k in app for k in ("stream", "video", "social", "learn", "education", "e-com", "ecom")) else "Telemetry Object Store"
        if "iot" in app or "device" in app:
            name = "Time-Series Store"
        if not any(c.type == "datastore" for c in new_arch.components):
            new_arch.components.append(Component(name=name, type="datastore", managed=True))
        return new_arch

    def _apply_add_auth_service(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Identity-Enforced")
        if not any(k in c.name.lower() for c in new_arch.components for k in ("auth", "identity", "cognito", "keycloak", "okta")):
            new_arch.components.append(Component(name="Auth Service", type="service", managed=False,
                                                properties={"reason": "Centralized identity enforcement"}))
        return new_arch

    def _apply_add_audit_logger(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Audit-Trailed")
        comp_reqs = getattr(req, "compliance_requirements", []) or []
        existing = [c for c in new_arch.components if "audit" in c.name.lower()]
        if not existing:
            name = f"Audit Logger ({', '.join(comp_reqs)})" if comp_reqs else "Audit Logger"
            new_arch.components.append(Component(name=name, type="security", managed=True))
        elif comp_reqs and not any(r.lower() in existing[0].name.lower() for r in comp_reqs):
            # Upgrade path: stamp the compliance standard onto the existing
            # logger so the audit trail is regulator-recognizable.
            existing[0].name = f"{existing[0].name} ({', '.join(comp_reqs)})"
            existing[0].managed = True
            new_arch.name = new_arch.name.replace("Audit-Trailed", "Compliance-Stamped")
        return new_arch

    def _apply_containerize(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Containerized")
        new_arch.deployment_strategy = "containerized"
        return new_arch

    def _apply_cost_guard(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        """Remove managed premiums where they buy little: self-host cache,
        messaging, compute and auxiliary stores; keep gateway/database/
        security managed (they carry reliability & compliance value)."""
        new_arch = self._clone_arch(arch, "Cost-Guarded")
        downgraded = 0
        for c in new_arch.components:
            if c.managed and str(c.type).lower() in ("cache", "messaging", "compute", "realtime", "datastore", "cdn"):
                c.managed = False
                c.properties = {**(c.properties or {}), "reason": "Cost guard: self-hosted non-critical tier"}
                downgraded += 1
        if downgraded == 0:
            # Nothing to guard: trim one redundant service tier instead.
            service_comps = [c for c in new_arch.components if c.type == "service"]
            if len(service_comps) > 4:
                new_arch.components = [c for c in new_arch.components if c.name != service_comps[-1].name]
        return new_arch

    def _apply_add_messaging(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        new_arch = self._clone_arch(arch, "Event-Driven")
        if not any(c.type == "messaging" for c in new_arch.components):
            new_arch.components.append(Component(name="RabbitMQ", type="messaging", managed=False))
        new_arch.communication_pattern = "event-driven"
        return new_arch

    def _apply_smart_replication(self, arch: Architecture, req: StructuredRequirements) -> Architecture:
        """Dual-instance key tiers: failover gains at ~1 extra instance of cost,
        not the tripling of the old 3× replication."""
        new_arch = self._clone_arch(arch, "Dual-Replicated")
        scaled = 0
        for c in new_arch.components:
            if scaled >= 3:
                break
            if c.type in ("service", "application", "database") and int(c.quantity or 1) < 2:
                c.quantity = 2
                c.properties = {**(c.properties or {}), "replication": "active-standby"}
                scaled += 1
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
        if len(service_comps) > 4:
            # Consolidate one service (only when genuinely oversized)
            to_remove = service_comps[-1]
            new_arch.components = [c for c in new_arch.components if c.name != to_remove.name]
        return new_arch
