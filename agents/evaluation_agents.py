from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .base import BaseAgent, AgentTraceEntry, LLMClient
from ..models.architecture import Architecture
from ..evaluation.cost_evaluator import CostEvaluator, EvaluatorResult as CostResult
from ..evaluation.security_evaluator import SecurityEvaluator, EvaluatorResult as SecurityResult
from ..evaluation.reliability_evaluator import ReliabilityEvaluator, EvaluatorResult as ReliabilityResult
from ..evaluation.performance_evaluator import PerformanceEvaluator, EvaluatorResult as PerformanceResult
from ..evaluation.scalability_evaluator import ScalabilityEvaluator, EvaluatorResult as ScalabilityResult
from ..fitness.fitness_engine import Candidate


class EvaluationAgentResult:
    """Standardized output from a specialized evaluation agent."""

    def __init__(
        self,
        dimension: str,
        score: float,
        strengths: List[str],
        weaknesses: List[str],
        reason: str,
    ):
        self.dimension = dimension
        self.score = float(score)
        self.strengths = list(strengths)
        self.weaknesses = list(weaknesses)
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "score": round(self.score, 2),
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "reason": self.reason,
        }


class CostEvaluationAgent(BaseAgent):
    """Specialized agent assessing infrastructure cost and operational overhead."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(name="Cost Evaluation Agent", role="Evaluates infrastructure and operational hosting costs", llm_client=llm_client)
        self._evaluator = CostEvaluator()

    def run(self, architecture: Architecture) -> EvaluationAgentResult:
        res = self._evaluator.evaluate(architecture)
        return EvaluationAgentResult(
            dimension="cost",
            score=res.score,
            strengths=res.strengths,
            weaknesses=res.weaknesses,
            reason=res.reason,
        )


class SecurityEvaluationAgent(BaseAgent):
    """Specialized agent assessing security posture, authentication, and perimeter controls."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(name="Security Evaluation Agent", role="Evaluates threat surface, authentication, and security boundaries", llm_client=llm_client)
        self._evaluator = SecurityEvaluator()

    def run(self, architecture: Architecture) -> EvaluationAgentResult:
        res = self._evaluator.evaluate(architecture)
        return EvaluationAgentResult(
            dimension="security",
            score=res.score,
            strengths=res.strengths,
            weaknesses=res.weaknesses,
            reason=res.reason,
        )


class ReliabilityEvaluationAgent(BaseAgent):
    """Specialized agent assessing redundancy, fault isolation, and disaster recovery."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(name="Reliability Evaluation Agent", role="Evaluates availability, redundancy, and failure isolation", llm_client=llm_client)
        self._evaluator = ReliabilityEvaluator()

    def run(self, architecture: Architecture) -> EvaluationAgentResult:
        res = self._evaluator.evaluate(architecture)
        return EvaluationAgentResult(
            dimension="reliability",
            score=res.score,
            strengths=res.strengths,
            weaknesses=res.weaknesses,
            reason=res.reason,
        )


class PerformanceEvaluationAgent(BaseAgent):
    """Specialized agent assessing latency, caching, and throughput."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(name="Performance Evaluation Agent", role="Evaluates response latency, caching efficiency, and throughput", llm_client=llm_client)
        self._evaluator = PerformanceEvaluator()

    def run(self, architecture: Architecture) -> EvaluationAgentResult:
        res = self._evaluator.evaluate(architecture)
        return EvaluationAgentResult(
            dimension="performance",
            score=res.score,
            strengths=res.strengths,
            weaknesses=res.weaknesses,
            reason=res.reason,
        )


class ScalabilityEvaluationAgent(BaseAgent):
    """Specialized agent assessing horizontal scalability and elastic buffering."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(name="Scalability Evaluation Agent", role="Evaluates horizontal elasticity, messaging buffering, and sharding", llm_client=llm_client)
        self._evaluator = ScalabilityEvaluator()

    def run(self, architecture: Architecture) -> EvaluationAgentResult:
        res = self._evaluator.evaluate(architecture)
        return EvaluationAgentResult(
            dimension="scalability",
            score=res.score,
            strengths=res.strengths,
            weaknesses=res.weaknesses,
            reason=res.reason,
        )


class MultiObjectiveEvaluatorAgent(BaseAgent):
    """Agent orchestrating all specialized evaluation agents and aggregating multi-objective results."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        super().__init__(
            name="Multi-Objective Evaluator Agent",
            role="Coordinates specialized evaluation agents and computes weighted fitness",
            llm_client=llm_client,
        )
        self.weights = weights or {
            "cost": 0.20,
            "security": 0.20,
            "reliability": 0.20,
            "performance": 0.20,
            "scalability": 0.20,
        }
        self.cost_agent = CostEvaluationAgent(llm_client)
        self.security_agent = SecurityEvaluationAgent(llm_client)
        self.reliability_agent = ReliabilityEvaluationAgent(llm_client)
        self.performance_agent = PerformanceEvaluationAgent(llm_client)
        self.scalability_agent = ScalabilityEvaluationAgent(llm_client)

    def evaluate_candidate(
        self,
        architecture: Architecture,
        generation: int = 0,
    ) -> Tuple[Candidate, Dict[str, EvaluationAgentResult], AgentTraceEntry]:
        """Run all specialized evaluators on an architecture and construct an evaluated Candidate."""
        cost_res = self.cost_agent.run(architecture)
        sec_res = self.security_agent.run(architecture)
        rel_res = self.reliability_agent.run(architecture)
        perf_res = self.performance_agent.run(architecture)
        scal_res = self.scalability_agent.run(architecture)

        eval_map = {
            "cost": cost_res,
            "security": sec_res,
            "reliability": rel_res,
            "performance": perf_res,
            "scalability": scal_res,
        }

        # Weighted fitness
        fitness = sum(eval_map[dim].score * self.weights.get(dim, 0.2) for dim in eval_map)

        candidate = Candidate(
            architecture=architecture,
            cost=cost_res.score,
            security=sec_res.score,
            reliability=rel_res.score,
            performance=perf_res.score,
            scalability=scal_res.score,
            overall_fitness=fitness,
            generation=generation,
            cost_reasoning=cost_res.reason,
            security_reasoning=sec_res.reason,
            reliability_reasoning=rel_res.reason,
            performance_reasoning=perf_res.reason,
            scalability_reasoning=scal_res.reason,
            evaluator_results=eval_map,
        )

        scores_summary = (
            f"Cost: {cost_res.score:.1f}, Sec: {sec_res.score:.1f}, "
            f"Rel: {rel_res.score:.1f}, Perf: {perf_res.score:.1f}, "
            f"Scal: {scal_res.score:.1f}"
        )

        trace = AgentTraceEntry(
            agent=self.name,
            action="Evaluate Candidate",
            architecture=architecture.name,
            reason=f"Multi-objective evaluation scored overall fitness {fitness:.1f}/100 ({scores_summary})",
            outcome="evaluated",
            fitness=fitness,
            generation=generation,
            details={
                "scores": {dim: eval_map[dim].score for dim in eval_map},
                "strengths": {dim: eval_map[dim].strengths for dim in eval_map},
                "weaknesses": {dim: eval_map[dim].weaknesses for dim in eval_map},
            },
        )

        return candidate, eval_map, trace

    def run(self, population: List[Architecture], generation: int = 0) -> Tuple[List[Candidate], List[AgentTraceEntry]]:
        """Evaluate a full population of architectures."""
        candidates: List[Candidate] = []
        traces: List[AgentTraceEntry] = []
        for arch in population:
            cand, _, trace = self.evaluate_candidate(arch, generation=generation)
            candidates.append(cand)
            traces.append(trace)
        return candidates, traces
