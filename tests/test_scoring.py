"""Tests for the production-grade scoring system.

Covers: earned-points differentiation (no saturation at 100),
requirement-conditioned scoring, application-aware + custom weights,
domain-specific parameters, and the verify-and-retry trace.
"""

from __future__ import annotations

import os
import tempfile

from archevolve.evaluation import evaluate_architecture
from archevolve.evaluation.domain_params import (
    EXTRA_SHARE,
    blended_weights,
    resolve_domain_params,
)
from archevolve.evaluation.scoring import resolve_weights
from archevolve.agents.base import LLMClient
from archevolve.models.architecture import ArchitectureModel


def _ctx(**kw):
    base = {"expected_users": 10000, "domain_services": ["X"],
            "domain_extras": {"security": [], "data": [], "realtime": []}, "assumptions": []}
    return base


CTX_BANK = {"expected_users": 1000000, "security_level": "high",
            "availability_percentage": 99.9, "application_type": "Online banking system",
            "compliance_requirements": ["pci-dss"]}
CTX_CHAT = {"expected_users": 50000, "security_level": "medium", "max_latency_ms": 80,
            "application_type": "Real-time chat application"}


class TestNoSaturation:
    def test_candidates_differentiate(self):
        mono = ArchitectureModel.create_monolith(_ctx())
        micro = ArchitectureModel.create_microservices(_ctx())
        r1 = evaluate_architecture(mono, context={"expected_users": 10000})
        r2 = evaluate_architecture(micro, context={"expected_users": 10000})
        assert r1.overall != r2.overall
        # No candidate may peg every dimension at 100
        for r in (r1, r2):
            scores = [r.cost, r.security, r.reliability, r.performance, r.scalability]
            assert not all(s == 100 for s in scores)
            assert all(0 <= s <= 100 for s in scores)

    def test_requirement_conditioning(self):
        mono = ArchitectureModel.create_monolith(_ctx())
        r_bank = evaluate_architecture(mono, context=CTX_BANK)
        r_chat = evaluate_architecture(mono, context=CTX_CHAT)
        # Same architecture, different requirements -> different overall
        assert r_bank.overall != r_chat.overall


class TestWeights:
    def test_auto_weights_sum_to_one(self):
        for app in ["Online banking system", "Real-time chat application",
                    "E-commerce platform", "IoT fleet", ""]:
            resolved = resolve_weights(app, None)
            assert abs(sum(resolved["weights"].values()) - 1.0) < 1e-6

    def test_domain_profiles_differ(self):
        bank = resolve_weights("Online banking system", None)["weights"]
        chat = resolve_weights("Real-time chat application", None)["weights"]
        assert bank["security"] > chat["security"]
        assert chat["performance"] > bank["performance"]

    def test_custom_weights_honored(self):
        mono = ArchitectureModel.create_monolith(_ctx())
        custom = {"cost": 0.5, "security": 0.1, "reliability": 0.1,
                  "performance": 0.15, "scalability": 0.15}
        r = evaluate_architecture(mono, context={"expected_users": 10000}, weights=custom)
        expected_core = (r.cost * 0.5 + r.security * 0.1 + r.reliability * 0.1
                         + r.performance * 0.15 + r.scalability * 0.15)
        # No domain extras for empty application_type -> overall == core
        assert abs(r.overall - expected_core) < 0.01


class TestDomainParams:
    def test_banking_has_extras_default_has_none(self):
        assert resolve_domain_params("Online banking system") == [
            "compliance_governance", "transactional_consistency"]
        assert resolve_domain_params("Real-time chat application") == [
            "realtime_delivery", "elastic_burst"]
        assert resolve_domain_params("") == []

    def test_blend_math(self):
        mono = ArchitectureModel.create_monolith(_ctx())
        r = evaluate_architecture(mono, context=CTX_BANK)
        assert set(r.domain_params) == {"compliance_governance", "transactional_consistency"}
        for v in r.domain_params.values():
            assert 0 <= v["score"] <= 100
            assert v["grade"] in "ABCDF"
            assert v["breakdown"]
        # Core weights are folded into the blended display dict; verify shares:
        assert abs(sum(r.weights.values()) - 1.0) < 1e-3
        extra_share = sum(v for k, v in r.weights.items() if k not in
                          ("cost", "security", "reliability", "performance", "scalability"))
        assert abs(extra_share - EXTRA_SHARE) < 0.02

    def test_blended_weights_sum(self):
        w = blended_weights({"cost": 0.2, "security": 0.2, "reliability": 0.2,
                             "performance": 0.2, "scalability": 0.2},
                            {"a": type("S", (), {"score": 50})(),
                             "b": type("S", (), {"score": 60})()})
        assert abs(sum(w.values()) - 1.0) < 1e-3


class TestVerifyAndRetry:
    def test_run_emits_verification_trace(self):
        from archevolve.agents.orchestrator import MultiAgentOrchestrator
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        try:
            orch = MultiAgentOrchestrator(
                population_size=3, max_generations=2, selection_count=2,
                mutation_count=1, experience_path=path,
                application_type="E-commerce platform", seed=42)
            results = orch.run("Build an e-commerce platform supporting 10,000 users.")
            actions = [t["action"] for t in results["agent_evolution_trace"]]
            assert "Verify Improvement" in actions
            assert "domain_params" in results
            assert results["domain_params"]
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestLLMClient:
    def test_deterministic_mode_never_calls_network(self):
        client = LLMClient(use_llm=False)
        assert client.complete("hello") == ""

    def test_llm_mode_without_key_falls_back(self):
        old = os.environ.pop("ARCHEVOLVE_LLM_API_KEY", None)
        try:
            client = LLMClient(use_llm=True)
            assert client.complete("hello") == ""
        finally:
            if old is not None:
                os.environ["ARCHEVOLVE_LLM_API_KEY"] = old


class TestHeuristicCeiling:
    """No parameter may ever read 100/100: static heuristics cannot verify
    runtime truth, so the top band is reserved for production-verified systems."""

    def _kitchen_sink(self):
        from archevolve.models.architecture import Architecture, Component
        comps = [
            Component(name="API Gateway", type="gateway", managed=True),
            Component(name="Load Balancer", type="gateway", managed=True),
            Component(name="WAF Firewall", type="security", managed=True),
            Component(name="Secrets Vault", type="security", managed=True),
            Component(name="Audit Logger (pci-dss)", type="security", managed=True),
            Component(name="KMS", type="security", managed=True),
            Component(name="Auth Service", type="service", quantity=2),
            Component(name="Ledger Service", type="service", quantity=2),
            Component(name="PostgreSQL", type="database", managed=True, quantity=2),
            Component(name="Redis Cache", type="cache", managed=True, quantity=2),
            Component(name="Kafka", type="messaging", managed=True, quantity=2),
            Component(name="Edge CDN", type="cdn", managed=True),
            Component(name="Media Object Store", type="datastore", managed=True),
        ]
        return Architecture(name="KitchenSink", components=comps,
                            communication_pattern="event-driven",
                            deployment_strategy="containerized")

    def _ctx(self):
        return {"expected_users": 1000000, "security_level": "high",
                "availability_percentage": 99.99, "max_latency_ms": 50,
                "application_type": "Online banking system",
                "compliance_requirements": ["pci-dss"]}

    def test_no_dimension_hits_100(self):
        r = evaluate_architecture(self._kitchen_sink(), context=self._ctx())
        scores = [r.cost, r.security, r.reliability, r.performance,
                  r.scalability, r.overall]
        scores += [v["score"] for v in r.domain_params.values()]
        assert scores, "expected scores to check"
        assert all(0 <= s <= 97 for s in scores)
        assert not any(s == 100 for s in scores)

    def test_ceiling_constant(self):
        from archevolve.evaluation.scoring import HEURISTIC_CEILING, apply_ceiling
        assert HEURISTIC_CEILING == 97.0
        assert apply_ceiling(100.0) == 97.0
        assert apply_ceiling(1000.0) == 97.0
        assert apply_ceiling(-5.0) == 0.0
        assert apply_ceiling(63.5) == 63.5

    def test_shared_result_type(self):
        from archevolve.evaluation.result import EvaluatorResult as Shared
        from archevolve.evaluation.cost_evaluator import EvaluatorResult as CostR
        from archevolve.evaluation.security_evaluator import EvaluatorResult as SecR
        assert CostR is Shared and SecR is Shared
        assert Shared(100.0).score == 97.0


class TestStrongMutations:
    def _parent(self, **kw):
        from archevolve.fitness.fitness_engine import Candidate
        from archevolve.models.architecture import Architecture, Component
        comps = [Component(name="API Gateway", type="gateway", managed=True),
                 Component(name="Shop Service", type="service"),
                 Component(name="PostgreSQL", type="database", managed=True)]
        arch = Architecture(name="P", components=comps)
        return Candidate(architecture=arch, cost=50, security=50, reliability=50,
                         performance=50, scalability=50, overall_fitness=50.0)

    def _req(self, app="Online banking system", **kw):
        from archevolve.agents.requirement_agent import RequirementAnalysisAgent
        agent = RequirementAnalysisAgent()
        s, _ = agent.run("Build system with " + app, app)
        return s

    def test_banking_domain_adds_audit(self):
        from archevolve.agents.mutation_agent import ArchitectureEvolutionAgent
        ag = ArchitectureEvolutionAgent(mutation_count=3, seed=1)
        muts, _ = ag.run(self._parent(), self._req(), {"successes": [], "failures": []}, 1)
        names = " ".join(c.name for m in muts for c in m.new_architecture.components)
        assert "audit" in names.lower()

    def test_chat_domain_adds_realtime_hub(self):
        from archevolve.agents.mutation_agent import ArchitectureEvolutionAgent
        ag = ArchitectureEvolutionAgent(mutation_count=3, seed=1)
        muts, _ = ag.run(self._parent(), self._req("Real-time chat application"),
                         {"successes": [], "failures": []}, 1)
        types = [c.type for m in muts for c in m.new_architecture.components]
        assert "realtime" in types or "messaging" in types

    def test_smart_replication_caps_at_two(self):
        from archevolve.agents.mutation_agent import ArchitectureEvolutionAgent
        ag = ArchitectureEvolutionAgent(mutation_count=1, seed=1)
        arch = ag._apply_smart_replication(self._parent().architecture, self._req())
        assert all(int(c.quantity or 1) <= 2 for c in arch.components)

    def test_retry_attempt_varies(self):
        from archevolve.agents.mutation_agent import ArchitectureEvolutionAgent
        ag = ArchitectureEvolutionAgent(mutation_count=2, seed=1)
        m0, _ = ag.run(self._parent(), self._req(), {"successes": [], "failures": []}, 1)
        m1, _ = ag.run(self._parent(), self._req(), {"successes": [], "failures": []}, 1,
                       attempt=1, focus="security")
        assert [m.new_architecture.name for m in m0] != [m.new_architecture.name for m in m1]
