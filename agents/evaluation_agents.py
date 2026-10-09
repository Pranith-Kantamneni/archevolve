from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .base import BaseAgent, AgentTraceEntry, LLMClient
from ..models.architecture import Architecture
from ..evaluation.cost_evaluator import CostEvaluator, EvaluatorResult as CostResult
from ..evaluation.security_evaluator import SecurityEvaluator, EvaluatorResult as SecurityResult
from ..evaluation.reliability_evaluator import ReliabilityEvaluator, EvaluatorResult as ReliabilityResult
from ..evaluation.performance_evaluator import PerformanceEvaluator, EvaluatorResult as PerformanceResult
from ..evaluation.scalability_evaluator import ScalabilityEvaluator, EvaluatorResult as ScalabilityResult
from ..evaluation.scoring import CORE_DIMENSIONS, ScoringContext, resolve_weights
from ..evaluation.domain_params import PARAM_DEFS, blend_overall, blended_weights, evaluate_domain_params
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
        breakdown: Optional[Dict[str, float]] = None,
        grade: str = "",
    ):
        self.dimension = dimension
        self.score = float(score)
        self.strengths = list(strengths)
        self.weaknesses = list(weaknesses)
        self.reason = reason
        self.breakdown = dict(breakdown or {})
        self.grade = grade

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "score": round(self.score, 2),
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "reason": self.reason,
            "breakdown": self.breakdown,
            "grade": self.grade,
        }


class CostEvaluationAgent(BaseAgent):
    """Specialized agent assessing infrastructure cost and operational overhead."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(name="Cost Evaluation Agent", role="Evaluates infrastructure and operational hosting costs", llm_client=llm_client)
        self._evaluator = CostEvaluator()

    def run(self, architecture: Architecture, context: Any = None) -> EvaluationAgentResult:
        res = self._evaluator.evaluate(architecture, context)
        return EvaluationAgentResult(
            dimension="cost",
            score=res.score,
            strengths=res.strengths,
            weaknesses=res.weaknesses,
            reason=res.reason,
            breakdown=res.breakdown,
            grade=res.grade,
        )


class SecurityEvaluationAgent(BaseAgent):
    """Specialized agent assessing security posture, authentication, and perimeter controls."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(name="Security Evaluation Agent", role="Evaluates threat surface, authentication, and security boundaries", llm_client=llm_client)
        self._evaluator = SecurityEvaluator()

    def run(self, architecture: Architecture, context: Any = None) -> EvaluationAgentResult:
        res = self._evaluator.evaluate(architecture, context)
        return EvaluationAgentResult(
            dimension="security",
            score=res.score,
            strengths=res.strengths,
            weaknesses=res.weaknesses,
            reason=res.reason,
            breakdown=res.breakdown,
            grade=res.grade,
        )


class ReliabilityEvaluationAgent(BaseAgent):
    """Specialized agent assessing redundancy, fault isolation, and disaster recovery."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(name="Reliability Evaluation Agent", role="Evaluates availability, redundancy, and failure isolation", llm_client=llm_client)
        self._evaluator = ReliabilityEvaluator()

    def run(self, architecture: Architecture, context: Any = None) -> EvaluationAgentResult:
        res = self._evaluator.evaluate(architecture, context)
        return EvaluationAgentResult(
            dimension="reliability",
            score=res.score,
            strengths=res.strengths,
            weaknesses=res.weaknesses,
            reason=res.reason,
            breakdown=res.breakdown,
            grade=res.grade,
        )


class PerformanceEvaluationAgent(BaseAgent):
    """Specialized agent assessing latency, caching, and throughput."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(name="Performance Evaluation Agent", role="Evaluates response latency, caching efficiency, and throughput", llm_client=llm_client)
        self._evaluator = PerformanceEvaluator()

    def run(self, architecture: Architecture, context: Any = None) -> EvaluationAgentResult:
        res = self._evaluator.evaluate(architecture, context)
        return EvaluationAgentResult(
            dimension="performance",
            score=res.score,
            strengths=res.strengths,
            weaknesses=res.weaknesses,
            reason=res.reason,
            breakdown=res.breakdown,
            grade=res.grade,
        )


class ScalabilityEvaluationAgent(BaseAgent):
    """Specialized agent assessing horizontal scalability and elastic buffering."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(name="Scalability Evaluation Agent", role="Evaluates horizontal elasticity, messaging buffering, and sharding", llm_client=llm_client)
        self._evaluator = ScalabilityEvaluator()

    def run(self, architecture: Architecture, context: Any = None) -> EvaluationAgentResult:
        res = self._evaluator.evaluate(architecture, context)
        return EvaluationAgentResult(
            dimension="scalability",
            score=res.score,
            strengths=res.strengths,
            weaknesses=res.weaknesses,
            reason=res.reason,
            breakdown=res.breakdown,
            grade=res.grade,
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
        self.weights = dict(weights) if weights is not None else None
        self.cost_agent = CostEvaluationAgent(llm_client)
        self.security_agent = SecurityEvaluationAgent(llm_client)
        self.reliability_agent = ReliabilityEvaluationAgent(llm_client)
        self.performance_agent = PerformanceEvaluationAgent(llm_client)
        self.scalability_agent = ScalabilityEvaluationAgent(llm_client)

    def _resolve_weights(self, context: Any, application_type: str) -> Dict[str, Any]:
        if self.weights is not None:
            total = sum(self.weights.values()) or 1.0
            norm = {k: float(v) / total for k, v in self.weights.items()}
            for dim in CORE_DIMENSIONS:
                norm.setdefault(dim, 0.0)
            return {"weights": norm, "profile": "custom", "source": "custom"}
        ctx = context if isinstance(context, ScoringContext) else ScoringContext.from_any(context, application_type)
        return resolve_weights(ctx.application_type or application_type, ctx)

    def evaluate_candidate(
        self,
        architecture: Architecture,
        generation: int = 0,
        context: Any = None,
        application_type: str = "",
    ) -> Tuple[Candidate, Dict[str, EvaluationAgentResult], AgentTraceEntry]:
        """Run all specialized evaluators on an architecture and construct an evaluated Candidate."""
        cost_res = self.cost_agent.run(architecture, context)
        sec_res = self.security_agent.run(architecture, context)
        rel_res = self.reliability_agent.run(architecture, context)
        perf_res = self.performance_agent.run(architecture, context)
        scal_res = self.scalability_agent.run(architecture, context)

        eval_map = {
            "cost": cost_res,
            "security": sec_res,
            "reliability": rel_res,
            "performance": perf_res,
            "scalability": scal_res,
        }

        # Application-aware weighted fitness (custom override or auto profile)
        resolved = self._resolve_weights(context, application_type)
        w = resolved["weights"]
        core_fitness = sum(eval_map[dim].score * w.get(dim, 0.2) for dim in eval_map)

        # Domain-specific parameters: evaluated from the same requirement
        # context and blended into overall fitness at EXTRA_SHARE.
        ctx = context if isinstance(context, ScoringContext) else ScoringContext.from_any(context, application_type)
        extras = evaluate_domain_params(architecture, ctx)
        fitness = blend_overall(core_fitness, extras)
        profile = resolved["profile"] + ("+domain" if extras else "")
        display_weights = blended_weights({dim: round(float(w.get(dim, 0.0)), 4) for dim in eval_map}, extras)

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
            breakdowns={dim: dict(eval_map[dim].breakdown) for dim in eval_map},
            grades={dim: eval_map[dim].grade for dim in eval_map},
            weights_used=display_weights,
            weight_profile=profile,
            extra_scores={k: round(v.score, 2) for k, v in extras.items()},
            extra_grades={k: v.grade for k, v in extras.items()},
            extra_breakdowns={k: dict(v.breakdown) for k, v in extras.items()},
        )

        scores_summary = (
            f"Cost: {cost_res.score:.1f}, Sec: {sec_res.score:.1f}, "
            f"Rel: {rel_res.score:.1f}, Perf: {perf_res.score:.1f}, "
            f"Scal: {scal_res.score:.1f}"
        )
        if extras:
            scores_summary += "".join(f", {PARAM_DEFS[k]['label']}: {v.score:.1f}" for k, v in extras.items())

        trace = AgentTraceEntry(
            agent=self.name,
            action="Evaluate Candidate",
            architecture=architecture.name,
            reason=f"Multi-objective evaluation scored overall fitness {fitness:.1f}/100 ({scores_summary}) [profile: {profile}]",
            outcome="evaluated",
            fitness=fitness,
            generation=generation,
            details={
                "scores": {dim: eval_map[dim].score for dim in eval_map},
                "strengths": {dim: eval_map[dim].strengths for dim in eval_map},
                "weaknesses": {dim: eval_map[dim].weaknesses for dim in eval_map},
                "breakdowns": {dim: eval_map[dim].breakdown for dim in eval_map},
                "grades": {dim: eval_map[dim].grade for dim in eval_map},
                "weights": display_weights,
                "weight_profile": profile,
                "domain_params": {k: {"label": PARAM_DEFS[k]["label"], "score": round(v.score, 2), "grade": v.grade, "breakdown": dict(v.breakdown)} for k, v in extras.items()},
            },
        )

        return candidate, eval_map, trace

    def run(
        self,
        population: List[Architecture],
        generation: int = 0,
        context: Any = None,
        application_type: str = "",
    ) -> Tuple[List[Candidate], List[AgentTraceEntry]]:
        """Evaluate a full population of architectures."""
        candidates: List[Candidate] = []
        traces: List[AgentTraceEntry] = []
        for arch in population:
            cand, _, trace = self.evaluate_candidate(
                arch, generation=generation, context=context, application_type=application_type
            )
            candidates.append(cand)
            traces.append(trace)
        return candidates, traces
