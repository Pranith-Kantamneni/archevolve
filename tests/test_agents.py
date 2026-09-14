from __future__ import annotations

import os
import tempfile
import pytest

from archevolve.agents.requirement_agent import RequirementAnalysisAgent, StructuredRequirements
from archevolve.agents.generation_agent import ArchitectureGenerationAgent
from archevolve.agents.evaluation_agents import (
    CostEvaluationAgent,
    SecurityEvaluationAgent,
    ReliabilityEvaluationAgent,
    PerformanceEvaluationAgent,
    ScalabilityEvaluationAgent,
    MultiObjectiveEvaluatorAgent,
)
from archevolve.agents.selection_agent import SelectionAgent
from archevolve.agents.mutation_agent import ArchitectureEvolutionAgent
from archevolve.agents.memory_agent import ExperienceMemoryAgent
from archevolve.agents.final_architecture_agent import FinalArchitectureAgent
from archevolve.agents.orchestrator import MultiAgentOrchestrator
from archevolve.models.architecture import Architecture, Component
from archevolve.fitness.fitness_engine import Candidate


class TestSpecializedAgents:
    """Unit tests validating each of the 7 specialized agent classes."""

    def test_requirement_analysis_agent(self):
        agent = RequirementAnalysisAgent()
        raw = "Build an e-commerce platform that supports 10,000 concurrent users with high security and low latency"
        structured, trace = agent.run(
            raw_requirement=raw,
            application_type="E-commerce platform",
            constraints={"provider": "aws", "max_budget": 5000},
        )
        assert isinstance(structured, StructuredRequirements)
        assert structured.expected_users == 10000
        assert structured.security_level == "high"
        assert structured.application_type == "E-commerce platform"
        assert trace.agent == "Requirement Analysis Agent"
        assert trace.outcome == "success"

    def test_architecture_generation_agent(self):
        req_agent = RequirementAnalysisAgent()
        structured, _ = req_agent.run("Build a real-time messaging application", "Chat")
        gen_agent = ArchitectureGenerationAgent()
        candidates, traces = gen_agent.run(structured, population_size=4, seed=42)
        assert len(candidates) == 4
        assert len(traces) == 4
        assert traces[0].agent == "Architecture Generation Agent"
        # Candidates should have meaningful component structures
        for arch in candidates:
            assert len(arch.components) > 0
            assert isinstance(arch.name, str)

    def test_evaluation_agents_detailed_output(self):
        arch = Architecture(
            name="Test Architecture",
            components=[
                Component(name="API Gateway", type="gateway", managed=True),
                Component(name="Redis Cache", type="cache", managed=True),
                Component(name="PostgreSQL", type="database", managed=True),
            ],
            communication_pattern="async",
        )

        cost_ag = CostEvaluationAgent()
        sec_ag = SecurityEvaluationAgent()
        rel_ag = ReliabilityEvaluationAgent()
        perf_ag = PerformanceEvaluationAgent()
        scal_ag = ScalabilityEvaluationAgent()

        for ag in [cost_ag, sec_ag, rel_ag, perf_ag, scal_ag]:
            res = ag.run(arch)
            assert 0 <= res.score <= 100
            assert isinstance(res.strengths, list)
            assert isinstance(res.weaknesses, list)
            assert isinstance(res.reason, str)
            assert len(res.reason) > 0

    def test_multi_objective_evaluator_agent(self):
        arch = Architecture(
            name="Test Microservices",
            components=[
                Component(name="Gateway", type="gateway", managed=True),
                Component(name="Service A", type="service", quantity=3),
                Component(name="Postgres", type="database", managed=True),
            ],
        )
        evaluator = MultiObjectiveEvaluatorAgent()
        cand, eval_map, trace = evaluator.evaluate_candidate(arch, generation=0)
        assert isinstance(cand, Candidate)
        assert 0 <= cand.overall_fitness <= 100
        assert len(eval_map) == 5
        assert trace.agent == "Multi-Objective Evaluator Agent"
        assert trace.outcome == "evaluated"

    def test_selection_agent_records_select_reject_reasons(self):
        cand1 = Candidate(architecture=Architecture(name="Arch Strong"), cost=85, security=90, reliability=85, performance=85, scalability=85, overall_fitness=86.0)
        cand2 = Candidate(architecture=Architecture(name="Arch Medium"), cost=75, security=70, reliability=70, performance=75, scalability=70, overall_fitness=72.0)
        cand3 = Candidate(architecture=Architecture(name="Arch Weak"), cost=50, security=50, reliability=50, performance=50, scalability=50, overall_fitness=50.0)

        selector = SelectionAgent()
        res, traces = selector.run([cand1, cand2, cand3], selection_count=2, generation=1)

        assert len(res.selected) == 2
        assert len(res.rejected) == 1
        assert res.selected[0].architecture.name == "Arch Strong"
        assert res.rejected[0].architecture.name == "Arch Weak"

        # Check explicit decision records
        assert len(res.decisions) == 3
        selected_decision = next(d for d in res.decisions if d.architecture_name == "Arch Strong")
        rejected_decision = next(d for d in res.decisions if d.architecture_name == "Arch Weak")
        assert selected_decision.selected is True
        assert "Selected" in selected_decision.reason
        assert rejected_decision.selected is False
        assert "Rejected" in rejected_decision.reason

    def test_experience_memory_agent_stores_successes_and_failures(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            mem_agent = ExperienceMemoryAgent(persistence_path=tmp_path)

            # Store a success
            _, s_trace = mem_agent.store_experience(
                architecture="Redis Cached Arch",
                application_type="E-commerce",
                requirements="High throughput",
                generation=1,
                evaluation_scores={"cost": 80, "performance": 90, "security": 85, "reliability": 85, "scalability": 85},
                fitness=85.0,
                outcome="success",
                reason="Adding Redis caching improved performance from 72 to 84 for read-heavy workload.",
                weaknesses=[],
                changes_made=["Added Redis cache layer"],
                improvements=["+12.0 performance"],
            )
            assert s_trace.outcome == "success"

            # Store a failure
            _, f_trace = mem_agent.store_experience(
                architecture="Heavy Microservices Arch",
                application_type="E-commerce",
                requirements="High throughput",
                generation=2,
                evaluation_scores={"cost": 55, "performance": 70, "security": 80, "reliability": 70, "scalability": 70},
                fitness=69.0,
                outcome="failure",
                reason="Adding an additional microservice increased infrastructure complexity and reduced the cost score from 82 to 55.",
                weaknesses=["high cost"],
                changes_made=["Added extra microservice"],
                improvements=[],
            )
            assert f_trace.outcome == "failure"

            # Query memory
            retrieved, q_trace = mem_agent.retrieve_experiences(application_type="E-commerce", limit=5)
            assert len(retrieved["successes"]) >= 1
            assert len(retrieved["failures"]) >= 1
            assert retrieved["successes"][0].architecture_name == "Redis Cached Arch"
            assert retrieved["failures"][0].architecture_name == "Heavy Microservices Arch"

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_mutation_agent_provenance(self):
        parent = Candidate(
            architecture=Architecture(name="Baseline Monolith", components=[Component(name="Core App", type="application")]),
            cost=80, security=60, reliability=60, performance=65, scalability=60, overall_fitness=65.0
        )
        req_agent = RequirementAnalysisAgent()
        structured, _ = req_agent.run("Build online banking system", "Banking")

        evolution_agent = ArchitectureEvolutionAgent(mutation_count=2, seed=42)
        mutations, traces = evolution_agent.run(
            parent=parent,
            requirements=structured,
            experiences={"successes": [], "failures": []},
            generation=1,
        )

        assert len(mutations) >= 1
        m = mutations[0]
        assert m.what_changed
        assert m.why_it_changed
        assert m.triggering_agent
        assert m.weakness_addressed
        assert m.parent_architecture_name == "Baseline Monolith"

    def test_multi_agent_orchestrator_end_to_end(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            orchestrator = MultiAgentOrchestrator(
                population_size=3,
                max_generations=2,
                selection_count=2,
                mutation_count=2,
                experience_path=tmp_path,
                application_type="E-commerce platform",
                seed=42,
            )
            results = orchestrator.run("Build an e-commerce platform supporting 10,000 users with secure payments and high availability.")

            assert "final_architecture" in results
            assert "baseline" in results
            assert "final_scores" in results
            assert "agent_evolution_trace" in results
            assert len(results["agent_evolution_trace"]) > 0

            # Verify participation of multiple distinct agents
            agents_seen = set(t["agent"] for t in results["agent_evolution_trace"])
            assert "Requirement Analysis Agent" in agents_seen
            assert "Architecture Generation Agent" in agents_seen
            assert "Multi-Objective Evaluator Agent" in agents_seen
            assert "Selection Agent" in agents_seen
            assert "Architecture Evolution Agent" in agents_seen
            assert "Experience Memory Agent" in agents_seen
            assert "Final Architecture Agent" in agents_seen

            # Verify successful and failed experiences are recorded in memory
            mem_entries = orchestrator.memory_agent.memory.entries
            assert any(e.outcome == "success" for e in mem_entries)
            assert any(e.outcome == "failure" for e in mem_entries)

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
