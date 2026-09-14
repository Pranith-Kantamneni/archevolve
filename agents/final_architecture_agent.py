from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .base import BaseAgent, AgentTraceEntry, LLMClient
from .requirement_agent import StructuredRequirements
from ..fitness.fitness_engine import Candidate
from ..models.graph import derive_connections


class FinalArchitectureAgent(BaseAgent):
    """Agent responsible for synthesizing the winning optimized architecture, rationale, and evolution report.

    Defined Input:
        - best_candidate: Winning Candidate from the multi-agent evolution loop.
        - baseline_candidate: Initial baseline candidate for comparison.
        - requirements: Structured requirements.
        - agent_trace: Full history of agent decisions.
        - generation_history: Generation-by-generation progression.

    Defined Output:
        - Final design report, rich design rationale, decision logs, and full API results.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(
            name="Final Architecture Agent",
            role="Synthesizes the optimal software architecture, documents design rationale, and generates evolution report",
            llm_client=llm_client,
        )

    def run(
        self,
        best_candidate: Candidate,
        baseline_candidate: Optional[Candidate],
        requirements: StructuredRequirements,
        agent_trace: List[AgentTraceEntry],
        generation_history: List[Dict[str, Any]],
        initial_candidates: List[Candidate],
        experience_memory_count: int = 0,
        experience_used: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], AgentTraceEntry]:
        """Produce the final optimized system architecture result."""
        arch = best_candidate.architecture

        baseline = None
        if baseline_candidate is not None:
            baseline = {
                "cost": round(baseline_candidate.cost, 2),
                "security": round(baseline_candidate.security, 2),
                "reliability": round(baseline_candidate.reliability, 2),
                "performance": round(baseline_candidate.performance, 2),
                "scalability": round(baseline_candidate.scalability, 2),
                "overall": round(baseline_candidate.overall_fitness, 2),
            }

        final_scores = {
            "cost": round(best_candidate.cost, 2),
            "security": round(best_candidate.security, 2),
            "reliability": round(best_candidate.reliability, 2),
            "performance": round(best_candidate.performance, 2),
            "scalability": round(best_candidate.scalability, 2),
            "overall": round(best_candidate.overall_fitness, 2),
        }

        improvement = {}
        if baseline:
            for obj in ["cost", "security", "reliability", "performance", "scalability"]:
                b_val = baseline[obj]
                f_val = final_scores[obj]
                abs_diff = f_val - b_val
                pct_diff = (abs_diff / max(b_val, 1e-10)) * 100
                improvement[obj] = {
                    "initial": b_val,
                    "final": f_val,
                    "absolute": round(abs_diff, 2),
                    "percentage": round(pct_diff, 2),
                }

        # Build comprehensive design rationale
        rationale_parts = []
        if arch.design_rationale:
            rationale_parts.append(arch.design_rationale)
        rationale_parts.append(
            f"Selected through {len(generation_history)} multi-agent evolutionary cycles, achieving a final multi-objective "
            f"fitness of {best_candidate.overall_fitness:.1f}/100. Incorporates {len(arch.components)} components tailored for "
            f"{requirements.application_type or 'high-performance systems'} with {arch.communication_pattern} messaging."
        )

        connections = derive_connections(arch.components, arch.communication_pattern, arch.services)

        serialized_initial = [
            {
                "name": c.architecture.name,
                "generation": c.generation,
                "fitness": round(c.overall_fitness, 2),
                "objective_scores": {
                    "cost": round(c.cost, 2),
                    "security": round(c.security, 2),
                    "reliability": round(c.reliability, 2),
                    "performance": round(c.performance, 2),
                    "scalability": round(c.scalability, 2),
                },
                "selected": bool(getattr(c, "selected_for_mutation", False)),
                "components": [
                    {"name": comp.name, "type": comp.type, "quantity": comp.quantity, "managed": comp.managed}
                    for comp in c.architecture.components
                ],
                "services": list(c.architecture.services),
                "communication_pattern": c.architecture.communication_pattern,
                "deployment_strategy": c.architecture.deployment_strategy,
            }
            for c in initial_candidates
        ]

        # Count total candidates evaluated
        total_eval = len(initial_candidates)
        for gen in generation_history:
            total_eval += len(gen.get("offspring", []))

        results: Dict[str, Any] = {
            "raw_requirement": requirements.raw_input,
            "application_type": requirements.application_type,
            "constraints": requirements.constraints,
            "parsed_requirements": {
                "functional": requirements.functional,
                "non_functional": requirements.non_functional,
                "expected_users": requirements.expected_users,
                "max_latency_ms": requirements.max_latency_ms,
                "availability_percentage": requirements.availability_percentage,
                "security_level": requirements.security_level,
                "data_encryption_required": requirements.data_encryption_required,
                "authentication_required": requirements.authentication_required,
                "scalability_type": requirements.scalability_type,
                "max_concurrent_streams": requirements.max_concurrent_streams,
                "cost_sensitive": requirements.cost_sensitive,
                "compliance_requirements": requirements.compliance_requirements,
                "deployment_environment": requirements.deployment_environment,
                "preferred_technologies": requirements.preferred_technologies,
                "max_monthly_cost": requirements.max_monthly_cost,
            },
            "baseline": baseline,
            "final_scores": final_scores,
            "improvement": improvement,
            "final_architecture": {
                "name": arch.name,
                "generation": arch.generation,
                "fitness": round(best_candidate.overall_fitness, 2),
                "cost": round(best_candidate.cost, 2),
                "security": round(best_candidate.security, 2),
                "reliability": round(best_candidate.reliability, 2),
                "performance": round(best_candidate.performance, 2),
                "scalability": round(best_candidate.scalability, 2),
                "overall_fitness": round(best_candidate.overall_fitness, 2),
                "services": list(arch.services),
                "communication_pattern": arch.communication_pattern,
                "deployment_strategy": arch.deployment_strategy,
                "design_rationale": " ".join(rationale_parts),
                "assumptions": list(arch.assumptions),
                "components": [
                    {
                        "name": comp.name,
                        "type": comp.type,
                        "quantity": comp.quantity,
                        "managed": comp.managed,
                    }
                    for comp in arch.components
                ],
                "connections": connections,
            },
            "initial_candidates": serialized_initial,
            "generation_history": generation_history,
            "evolution_history": {
                "generations_run": max(0, len(generation_history) - 1),
                "population_size": len(initial_candidates),
                "candidates_evaluated": total_eval,
                "fitness_progression": [g.get("best_fitness") for g in generation_history if g.get("best_fitness") is not None],
            },
            "agent_evolution_trace": [t.to_dict() for t in agent_trace],
            "agent_trace": [t.to_dict() for t in agent_trace],  # alias
            "experience_memory_entries": experience_memory_count,
            "experience_used": list(experience_used or []),
        }

        trace = AgentTraceEntry(
            agent=self.name,
            action="Finalize Architecture",
            architecture=arch.name,
            reason=f"Synthesized winning architecture '{arch.name}' with overall fitness {best_candidate.overall_fitness:.1f}/100.",
            outcome="finalized",
            fitness=best_candidate.overall_fitness,
            generation=arch.generation,
            details={
                "components_count": len(arch.components),
                "final_fitness": best_candidate.overall_fitness,
                "baseline_fitness": baseline["overall"] if baseline else None,
            },
        )

        return results, trace
