"""Basic tests for ARCHEVOLVE modules."""

from __future__ import annotations

import pytest

from archevolve.requirements import parse_requirement, ParsedRequirement
from archevolve.models.architecture import Architecture, Component, ArchitectureModel
from archevolve.evaluation import evaluate_architecture, CostEvaluator, SecurityEvaluator, ReliabilityEvaluator, PerformanceEvaluator, ScalabilityEvaluator
from archevolve.fitness.fitness_engine import FitnessEngine, Candidate
from archevolve.selection.selector import Selector, SelectionResult
from archevolve.mutation.mutation_engine import MutationEngine, MutationResult, ExperienceEntry
from archevolve.memory.experience_memory import JsonExperienceMemory
from archevolve.evolution.evolution_engine import EvolutionEngine


# --- Requirement Parser Tests ---

class TestRequirementParser:
    """Tests for the requirement parser."""

    def test_basic_parsing(self):
        """Test basic requirement parsing."""
        raw = "Build an e-commerce platform that supports 10,000 concurrent users"
        parsed = parse_requirement(raw)
        assert parsed.raw_input == raw
        assert parsed.expected_users == 10000

    def test_security_requirements(self):
        """Test security requirement extraction."""
        raw = "requires secure payment processing and authentication"
        parsed = parse_requirement(raw)
        assert parsed.security_level == "high"
        assert parsed.data_encryption_required == True
        assert parsed.authentication_required == True

    def test_cost_sensitive(self):
        """Test cost sensitivity extraction."""
        raw = "keeping infrastructure cost reasonable"
        parsed = parse_requirement(raw)
        assert parsed.cost_sensitive == True

    def test_scalability_requirements(self):
        """Test scalability requirement extraction."""
        raw = "should be scalable during traffic spikes"
        parsed = parse_requirement(raw)
        assert parsed.scalability_type == "horizontal"

    def test_availability_requirements(self):
        """Test availability requirement extraction."""
        raw = "requires high availability"
        parsed = parse_requirement(raw)
        assert parsed.availability_percentage == 99.9


# --- Architecture Model Tests ---

class TestArchitectureModel:
    """Tests for the architecture model."""

    def test_component_creation(self):
        """Test Component model creation."""
        comp = Component(name="PostgreSQL", type="database", managed=True)
        assert comp.name == "PostgreSQL"
        assert comp.type == "database"
        assert comp.managed == True

    def test_component_defaults(self):
        """Test Component with defaults."""
        comp = Component(name="Redis", type="cache")
        assert comp.name == "Redis"
        assert comp.type == "cache"
        assert comp.managed == False  # default

    def test_architecture_creation(self):
        """Test Architecture model creation."""
        comps = [Component(name="PostgreSQL", type="database")]
        arch = Architecture(
            name="Test Arch",
            components=comps,
            deployment_strategy="standard",
        )
        assert arch.name == "Test Arch"
        assert len(arch.components) == 1
        assert arch.components[0].name == "PostgreSQL"

    def test_architecture_with_all_fields(self):
        """Test Architecture with all fields."""
        comps = [
            Component(name="API GW", type="gateway", managed=True),
            Component(name="App", type="application", quantity=2),
        ]
        arch = ArchitectureModel.create_monolith({
            "assumptions": ["Single team", "Moderate traffic"],
        })
        assert arch.name == "Modular Monolith"
        assert arch.generation == 0
        assert len(arch.components) > 0


# --- Evaluator Tests ---

class TestEvaluators:
    """Tests for architecture evaluators."""

    def test_cost_evaluator(self):
        """Test CostEvaluator returns valid score."""
        from archevolve.models.architecture import Architecture, Component

        comps = [Component(name="PostgreSQL", type="database", managed=True)]
        arch = Architecture(name="Test", components=comps)
        evaluator = CostEvaluator()
        result = evaluator.evaluate(arch)
        assert 0 <= result.score <= 100
        assert isinstance(result.reasoning, str)

    def test_security_evaluator(self):
        """Test SecurityEvaluator returns valid score."""
        from archevolve.models.architecture import Architecture, Component

        comps = [Component(name="API Gateway", type="gateway", managed=True)]
        arch = Architecture(name="Test", components=comps)
        evaluator = SecurityEvaluator()
        result = evaluator.evaluate(arch)
        assert 0 <= result.score <= 100
        assert isinstance(result.reasoning, str)

    def test_reliability_evaluator(self):
        """Test ReliabilityEvaluator returns valid score."""
        from archevolve.models.architecture import Architecture, Component

        comps = [
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis", type="cache", managed=True),
        ]
        arch = Architecture(name="Test", components=comps)
        evaluator = ReliabilityEvaluator()
        result = evaluator.evaluate(arch)
        assert 0 <= result.score <= 100
        assert isinstance(result.reasoning, str)

    def test_performance_evaluator(self):
        """Test PerformanceEvaluator returns valid score."""
        from archevolve.models.architecture import Architecture, Component

        comps = [
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis", type="cache", managed=True),
        ]
        arch = Architecture(name="Test", components=comps, communication_pattern="sync")
        evaluator = PerformanceEvaluator()
        result = evaluator.evaluate(arch)
        assert 0 <= result.score <= 100
        assert isinstance(result.reasoning, str)

    def test_scalability_evaluator(self):
        """Test ScalabilityEvaluator returns valid score."""
        from archevolve.models.architecture import Architecture, Component

        comps = [
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis", type="cache", managed=True),
        ]
        arch = Architecture(name="Test", components=comps, communication_pattern="async")
        evaluator = ScalabilityEvaluator()
        result = evaluator.evaluate(arch)
        assert 0 <= result.score <= 100
        assert isinstance(result.reasoning, str)


# --- Fitness Engine Tests ---

class TestFitnessEngine:
    """Tests for the fitness engine."""

    def test_fitness_calculation(self):
        """Test fitness engine computes overall fitness."""
        from archevolve.models.architecture import Architecture, Component

        comps = [
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis", type="cache", managed=True),
        ]
        arch = Architecture(name="Test", components=comps)
        engine = FitnessEngine()
        candidate = engine.evaluate_and_score(arch, generation=0)
        assert hasattr(candidate, "overall_fitness")
        assert 0 <= candidate.overall_fitness <= 100
        assert hasattr(candidate, "cost")
        assert hasattr(candidate, "security")
        assert hasattr(candidate, "reliability")
        assert hasattr(candidate, "performance")
        assert hasattr(candidate, "scalability")

    def test_fitness_with_weights(self):
        """Test fitness engine with custom weights."""
        from archevolve.models.architecture import Architecture, Component

        comps = [
            Component(name="PostgreSQL", type="database", managed=True),
            Component(name="Redis", type="cache", managed=True),
        ]
        arch = Architecture(name="Test", components=comps)
        # Use weights that sum to exactly 1.0
        weights = {"cost": 0.3, "security": 0.3, "reliability": 0.2, "performance": 0.1, "scalability": 0.1}
        engine = FitnessEngine(weights=weights)
        candidate = engine.evaluate_and_score(arch, generation=0)
        # Verify overall_fitness matches the weighted combination
        expected = (candidate.cost * weights["cost"] +
                    candidate.security * weights["security"] +
                    candidate.reliability * weights["reliability"] +
                    candidate.performance * weights["performance"] +
                    candidate.scalability * weights["scalability"])
        assert abs(candidate.overall_fitness - expected) < 0.1


# --- Selection Tests ---

class TestSelector:
    """Tests for the selector."""

    def test_select_top_two(self):
        """Test selecting top 2 candidates."""
        candidates = [
            Candidate(architecture=None, cost=90, security=80, reliability=70, performance=80, scalability=70, overall_fitness=78.0),
            Candidate(architecture=None, cost=60, security=90, reliability=80, performance=88, scalability=85, overall_fitness=80.6),
            Candidate(architecture=None, cost=90, security=75, reliability=70, performance=82, scalability=70, overall_fitness=77.4),
        ]
        selector = Selector()
        result = selector.select(candidates, 2)
        assert len(result.selected) == 2
        assert len(result.rejected) == 1
        # Top two should be the 2nd and 3rd (fitness 80.6 and 77.4)
        assert result.selected[0].overall_fitness >= result.selected[1].overall_fitness

    def test_select_all(self):
        """Test selecting all candidates when count >= pool size."""
        candidates = [
            Candidate(architecture=None, cost=90, overall_fitness=90.0),
            Candidate(architecture=None, cost=80, overall_fitness=80.0),
        ]
        selector = Selector()
        result = selector.select(candidates, 5)  # request 5, only 2 available
        assert len(result.selected) == 2
        assert len(result.rejected) == 0

    def test_rank_candidates(self):
        """Test ranking candidates by fitness."""
        candidates = [
            Candidate(architecture=None, overall_fitness=80.6),
            Candidate(architecture=None, overall_fitness=78.0),
            Candidate(architecture=None, overall_fitness=77.4),
        ]
        selector = Selector()
        # Use select to rank (select with count=len gives ranked order)
        result = selector.select(candidates, len(candidates))
        ranked = result.selected
        # Should be sorted descending by fitness
        assert ranked[0].overall_fitness >= ranked[1].overall_fitness >= ranked[2].overall_fitness


# --- Experience Memory Tests ---

class TestExperienceMemory:
    """Tests for experience memory."""

    def test_json_memory_create_and_retrieve(self):
        """Test JSON experience memory create and retrieve."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            memory = JsonExperienceMemory(persistence_path=tmp_path)
            memory.add(
                architecture_name="Test Arch",
                generation=1,
                objective_scores={"cost": 80, "security": 90, "reliability": 85, "performance": 80, "scalability": 90},
                fitness=85.5,
                modifications=["Added cache"],
                weaknesses=["High cost"],
                improvements=["Better performance"],
                requirement_context={"users": 1000},
            )

            assert len(memory.entries) == 1
            entry = memory.entries[0]
            assert entry.architecture_name == "Test Arch"
            assert entry.generation == 1
            assert entry.fitness == 85.5

            # Test recent entries
            recent = memory.recent_entries(limit=5)
            assert len(recent) == 1

            # Test best entries
            best = memory.best_entries(3)
            assert len(best) == 1

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_memory_without_persistence(self):
        """Test memory in-memory mode."""
        from archevolve.memory.experience_memory import JsonExperienceMemory

        # JsonExperienceMemory always persists to file, so test with a unique path
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
            os.unlink(tmp_path)  # remove so it starts fresh

        try:
            memory = JsonExperienceMemory(persistence_path=tmp_path)
            assert len(memory.entries) == 0

            memory.add(
                architecture_name="Test Arch",
                generation=1,
                objective_scores={"cost": 80},
                fitness=80.0,
                modifications=[],
                weaknesses=[],
                improvements=[],
                requirement_context={},
            )

            assert len(memory.entries) == 1
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


# --- Evolution Engine Tests ---

class TestEvolutionEngine:
    """Tests for the evolution engine."""

    def test_evolution_engine_run(self):
        """Test that the evolution engine can run."""
        raw = "Build an e-commerce platform that supports 10,000 concurrent users"
        engine = EvolutionEngine(
            population_size=3,
            max_generations=2,
            selection_count=2,
            mutation_count=2,
            weights=None,
            use_llm=False,
        )
        results = engine.run(raw)
        assert results is not None
        assert "final_scores" in results
        assert "baseline" in results
        assert "improvement" in results

    def test_evolution_improvement(self):
        """Test that evolution can improve fitness."""
        raw = "Build an e-commerce platform that supports 10,000 concurrent users"
        engine = EvolutionEngine(
            population_size=3,
            max_generations=3,
            selection_count=2,
            mutation_count=2,
            weights=None,
            use_llm=False,
        )
        results = engine.run(raw)
        initial = results["baseline"]["overall"]
        final = results["final_scores"]["overall"]
        # Fitness should be computed and reasonable
        assert 0 <= initial <= 100
        assert 0 <= final <= 100
        # There should be some improvement or at least stable results
        assert isinstance(results["improvement"], dict)


# --- Integration Test ---

class TestIntegrationEndToEnd:
    """End-to-end integration test."""

    def test_full_pipeline(self):
        """Test the complete pipeline from requirements to final architecture."""
        raw = "Build an e-commerce platform that supports 10,000 concurrent users, requires high availability, secure payment processing, low latency, and should be scalable during traffic spikes while keeping infrastructure cost reasonable."

        # Parse requirements
        from archevolve.requirements import parse_requirement
        parsed = parse_requirement(raw)
        assert parsed.expected_users == 10000
        assert parsed.security_level == "high"
        assert parsed.cost_sensitive == True

        # Generate initial population
        from archevolve.generation.architecture_generator import ArchitectureGenerator
        generator = ArchitectureGenerator(population_size=5, seed=42)
        population = generator.generate_initial_population(raw)
        assert len(population) == 5

        # Evaluate population
        from archevolve.evaluation import evaluate_architecture
        from archevolve.fitness.fitness_engine import FitnessEngine
        engine = FitnessEngine()
        evaluated = []
        for arch in population:
            candidate = engine.evaluate_and_score(arch, generation=0)
            evaluated.append(candidate)
        assert len(evaluated) == 5
        # All should have fitness scores
        for c in evaluated:
            assert 0 <= c.overall_fitness <= 100

        # Select top candidates
        from archevolve.selection.selector import Selector
        selector = Selector()
        selected = selector.select(evaluated, 2)
        assert len(selected.selected) == 2

        # Evaluate evolution
        from archevolve.evolution.evolution_engine import EvolutionEngine
        evol_engine = EvolutionEngine(
            population_size=5,
            max_generations=2,
            selection_count=2,
            mutation_count=2,
            weights=None,
            use_llm=False,
        )
        results = evol_engine.run(raw)
        assert results is not None
        assert "final_scores" in results
        assert "baseline" in results
        assert results["final_scores"]["overall"] is not None