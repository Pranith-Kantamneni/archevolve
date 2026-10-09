from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import AgentTraceEntry, LLMClient
from .requirement_agent import RequirementAnalysisAgent, StructuredRequirements
from .generation_agent import ArchitectureGenerationAgent
from .evaluation_agents import MultiObjectiveEvaluatorAgent
from .selection_agent import SelectionAgent
from .mutation_agent import ArchitectureEvolutionAgent, ArchitectureMutation
from .memory_agent import ExperienceMemoryAgent
from .final_architecture_agent import FinalArchitectureAgent
from ..fitness.fitness_engine import Candidate


def _stable_seed(text: str) -> int:
    """Derive a deterministic seed from the input description."""
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _comm_of(arch: Any) -> str:
    if isinstance(arch, dict):
        return str(arch.get("communication_pattern", "") or "")
    return str(getattr(arch, "communication_pattern", "") or "")


def _deploy_of(arch: Any) -> str:
    if isinstance(arch, dict):
        return str(arch.get("deployment_strategy", "") or "")
    return str(getattr(arch, "deployment_strategy", "") or "")


class MultiAgentOrchestrator:
    """Coordinates the specialized agents through the complete evolutionary architecture pipeline."""

    def __init__(
        self,
        population_size: int = 5,
        max_generations: int = 5,
        selection_count: int = 2,
        mutation_count: int = 2,
        weights: Optional[Dict[str, float]] = None,
        use_llm: bool = False,
        experience_path: str = "experience_memory.json",
        stopping_threshold: Optional[float] = None,
        stagnation_limit: int = 2,
        application_type: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
        llm_model: Optional[str] = None,
    ):
        self.population_size = population_size
        self.max_generations = max_generations
        self.selection_count = selection_count
        self.mutation_count = mutation_count
        self.use_llm = use_llm
        self.stagnation_limit = stagnation_limit
        self.application_type = application_type or ""
        self.constraints = constraints or {}
        self.stopping_threshold = stopping_threshold

        seed_text = json.dumps(
            {"app": self.application_type or "", "constraints": self.constraints},
            sort_keys=True,
        )
        self.seed = seed if seed is not None else _stable_seed(seed_text)

        self.llm_client = LLMClient(use_llm=use_llm, model=llm_model)

        # Initialize the 7 specialized agents
        self.requirement_agent = RequirementAnalysisAgent(self.llm_client)
        self.generation_agent = ArchitectureGenerationAgent(self.llm_client)
        self.evaluator_agent = MultiObjectiveEvaluatorAgent(weights=weights, llm_client=self.llm_client)
        self.selection_agent = SelectionAgent(self.llm_client)
        self.evolution_agent = ArchitectureEvolutionAgent(
            mutation_count=mutation_count, seed=self.seed, llm_client=self.llm_client
        )
        self.memory_agent = ExperienceMemoryAgent(
            persistence_path=experience_path, llm_client=self.llm_client
        )
        self.final_agent = FinalArchitectureAgent(self.llm_client)

        # Orchestration state
        self.agent_trace: List[AgentTraceEntry] = []
        self.generation_history: List[Dict[str, Any]] = []
        self.experience_used: List[str] = []

    def _log_trace(self, trace_entries: List[AgentTraceEntry] | AgentTraceEntry) -> None:
        if isinstance(trace_entries, list):
            self.agent_trace.extend(trace_entries)
        else:
            self.agent_trace.append(trace_entries)

    def run(self, raw_requirement: str) -> Dict[str, Any]:
        """Execute the multi-agent evolution loop from requirements to final architecture."""
        # 1. Requirement Analysis Agent
        structured_req, req_trace = self.requirement_agent.run(
            raw_requirement=raw_requirement,
            application_type=self.application_type,
            constraints=self.constraints,
        )
        self._log_trace(req_trace)

        # 2. Architecture Generation Agent
        raw_candidates, gen_traces = self.generation_agent.run(
            requirements=structured_req,
            population_size=self.population_size,
            seed=self.seed,
        )
        self._log_trace(gen_traces)

        # 3. Evaluation Agents (Initial Population)
        population, eval_traces = self.evaluator_agent.run(
            raw_candidates,
            generation=0,
            context=structured_req,
            application_type=self.application_type,
        )
        self._log_trace(eval_traces)

        initial_population_evaluated = list(population)
        best_candidate = max(population, key=lambda c: c.overall_fitness)
        # Honest baseline: the BEST initial candidate, not population[0].
        # Improvement claims must measure evolution's work, not lucky ordering.
        baseline_candidate = best_candidate

        # Record Gen 0 in generation history
        gen_0_record: Dict[str, Any] = {
            "generation": 0,
            "population_size": len(population),
            "best_fitness": round(best_candidate.overall_fitness, 2),
            "best_architecture": best_candidate.architecture.name,
            "population": [self._candidate_to_dict(c) for c in population],
        }
        self.generation_history.append(gen_0_record)

        # Store baseline experiences in memory (adaptive threshold: absolute
        # floor of 65.0 or the population median, whichever is higher -- the
        # earned-points rubric rarely yields 70+ for unevolved candidates).
        import statistics as _stats

        _gen0_scores = [c.overall_fitness for c in population] or [0.0]
        _success_floor = max(65.0, float(_stats.median(_gen0_scores)))
        for cand in population:
            outcome = "success" if cand.overall_fitness >= _success_floor else "failure"
            if outcome == "success":
                reason = f"Candidate '{cand.architecture.name}' demonstrated baseline feasibility with fitness {cand.overall_fitness:.1f}."
            else:
                reason = f"Candidate '{cand.architecture.name}' exhibited baseline limitations (fitness {cand.overall_fitness:.1f})."

            _, mem_trace = self.memory_agent.store_experience(
                architecture=cand.architecture.name,
                application_type=self.application_type,
                requirements=raw_requirement,
                generation=0,
                evaluation_scores={
                    "cost": cand.cost,
                    "security": cand.security,
                    "reliability": cand.reliability,
                    "performance": cand.performance,
                    "scalability": cand.scalability,
                },
                fitness=cand.overall_fitness,
                outcome=outcome,
                reason=reason,
                weaknesses=[f"low score on {k}" for k, v in [("cost", cand.cost), ("security", cand.security), ("reliability", cand.reliability), ("performance", cand.performance), ("scalability", cand.scalability)] if v < 70],
                changes_made=[],
                improvements=[],
                experience_used=[],
            )
            self._log_trace(mem_trace)

        # Evolutionary loop
        generation = 0
        stagnation_counter = 0
        evaluation_history: List[float] = [c.overall_fitness for c in population]

        while generation < self.max_generations:
            generation += 1

            # 4. Selection Agent
            selection_res, sel_traces = self.selection_agent.run(
                candidates=population,
                selection_count=self.selection_count,
                generation=generation,
            )
            self._log_trace(sel_traces)

            # Check stopping threshold on selection
            if self.stopping_threshold and selection_res.selected:
                if selection_res.selected[0].overall_fitness >= self.stopping_threshold:
                    break

            # 5. Experience Memory Agent (Retrieve relevant past successes & failures)
            retrieved_experiences, ret_trace = self.memory_agent.retrieve_experiences(
                application_type=self.application_type,
                weaknesses=[],
                limit=3,
                generation=generation,
            )
            self._log_trace(ret_trace)

            # 6. Architecture Evolution / Mutation Agent
            offspring_records: List[Dict[str, Any]] = []
            new_offspring_candidates: List[Candidate] = []
            seen_signatures: Set[str] = set()

            for parent_cand in selection_res.selected:
                mutations, mut_traces = self.evolution_agent.run(
                    parent=parent_cand,
                    requirements=structured_req,
                    experiences=retrieved_experiences,
                    generation=generation,
                )
                self._log_trace(mut_traces)

                # 7. Evaluation Agents (Evaluate offspring, verify improvement)
                for mut in mutations:
                    child_cand, delta = self._evaluate_record_mutation(
                        mut, parent_cand, generation, structured_req,
                        raw_requirement, offspring_records,
                        new_offspring_candidates, seen_signatures,
                    )
                    # 7b. Retry when the mutation did not improve OR when it
                    # improved overall but cratered a dimension (harm-gated):
                    # try a different pattern focused on the weakest/cratered dim.
                    harmful = getattr(mut, "harmful_dim", None)
                    if child_cand is not None and (delta <= 0 or harmful):
                        focus = harmful or self._weakest_dimension(parent_cand)
                        why = (f"Child fitness did not improve ({delta:+.1f})"
                               if delta <= 0 else
                               f"Child improved overall ({delta:+.1f}) but cratered '{harmful}'")
                        retry_muts, retry_traces = self.evolution_agent.run(
                            parent=parent_cand,
                            requirements=structured_req,
                            experiences=retrieved_experiences,
                            generation=generation,
                            attempt=1,
                            focus=focus,
                        )
                        for rm in retry_muts:
                            rm.why_it_changed = f"Retry (focus: {focus}): " + rm.why_it_changed
                        self._log_trace(retry_traces)
                        self._log_trace(AgentTraceEntry(
                            agent="Architecture Evolution Agent",
                            action="Retry Mutation",
                            architecture=parent_cand.architecture.name,
                            reason=why + f"; retrying with different pattern(s) focused on '{focus}'.",
                            outcome="retried",
                            fitness=parent_cand.overall_fitness,
                            generation=generation,
                            details={"focus_dimension": focus, "attempt": 1},
                        ))
                        for rm in retry_muts:
                            self._evaluate_record_mutation(
                                rm, parent_cand, generation, structured_req,
                                raw_requirement, offspring_records,
                                new_offspring_candidates, seen_signatures,
                            )

            if not new_offspring_candidates:
                break

            # Form next generation population (elitist selection + offspring)
            population = selection_res.selected + new_offspring_candidates
            current_best = max(population, key=lambda c: c.overall_fitness)

            # Record generation details
            gen_record = {
                "generation": generation,
                "population_size": len(population),
                "best_fitness": round(current_best.overall_fitness, 2),
                "best_architecture": current_best.architecture.name,
                "population": [self._candidate_to_dict(c) for c in population],
                "selected": [self._candidate_to_dict(c) for c in selection_res.selected],
                "offspring": offspring_records,
            }
            self.generation_history.append(gen_record)

            # Track stagnation (against history BEFORE this generation)
            best_so_far = max(evaluation_history, default=0.0)
            is_new_best = current_best.overall_fitness > best_so_far + 1e-9
            evaluation_history.append(current_best.overall_fitness)

            if is_new_best:
                stagnation_counter = 0
                best_candidate = current_best
            else:
                stagnation_counter += 1

            if stagnation_counter >= self.stagnation_limit:
                break

        # Final best candidate
        best_candidate = max(population, key=lambda c: c.overall_fitness)

        # 9b. Recovery rounds: if evolution never beat the baseline, try harder
        # (different patterns, weakest-dim focus) and trace every attempt.
        recovery_rounds = 0
        while recovery_rounds < 2 and best_candidate.overall_fitness <= baseline_candidate.overall_fitness:
            recovery_rounds += 1
            weakest = self._weakest_dimension(best_candidate)
            rec_muts, rec_traces = self.evolution_agent.run(
                parent=best_candidate,
                requirements=structured_req,
                experiences={"successes": [], "failures": []},
                generation=generation + recovery_rounds,
                attempt=recovery_rounds,
                focus=weakest,
            )
            for rm in rec_muts:
                rm.why_it_changed = f"Recovery round {recovery_rounds} (target: {weakest}): " + rm.why_it_changed
            self._log_trace(rec_traces)
            self._log_trace(AgentTraceEntry(
                agent="Architecture Evolution Agent",
                action="Recovery Mutation",
                architecture=best_candidate.architecture.name,
                reason=f"Best fitness {best_candidate.overall_fitness:.1f} did not beat baseline {baseline_candidate.overall_fitness:.1f}; recovery round {recovery_rounds} targeting '{weakest}'.",
                outcome="recovery",
                fitness=best_candidate.overall_fitness,
                generation=generation + recovery_rounds,
                details={"weakest_dimension": weakest, "round": recovery_rounds},
            ))
            rec_records: List[Dict[str, Any]] = []
            rec_children: List[Candidate] = []
            rec_seen: Set[str] = set()
            for rm in rec_muts:
                self._evaluate_record_mutation(
                    rm, best_candidate, generation + recovery_rounds,
                    structured_req, raw_requirement, rec_records,
                    rec_children, rec_seen,
                )
            if rec_children:
                improved = max(rec_children, key=lambda c: c.overall_fitness)
                self.generation_history.append({
                    "generation": generation + recovery_rounds,
                    "population_size": len(rec_children) + 1,
                    "best_fitness": round(max(best_candidate.overall_fitness, improved.overall_fitness), 2),
                    "best_architecture": (improved if improved.overall_fitness > best_candidate.overall_fitness else best_candidate).architecture.name,
                    "population": [self._candidate_to_dict(best_candidate)] + [self._candidate_to_dict(c) for c in rec_children],
                    "selected": [self._candidate_to_dict(best_candidate)],
                    "offspring": rec_records,
                    "recovery": True,
                })
                generation += 1
                if improved.overall_fitness > best_candidate.overall_fitness:
                    best_candidate = improved

        # 9c. Explicit end-of-run verification: are parameters increasing?
        self._log_trace(self._verification_trace(best_candidate, baseline_candidate))

        # 10. Final Architecture Agent
        results, final_trace = self.final_agent.run(
            best_candidate=best_candidate,
            baseline_candidate=baseline_candidate,
            requirements=structured_req,
            agent_trace=self.agent_trace,
            generation_history=self.generation_history,
            initial_candidates=initial_population_evaluated,
            experience_memory_count=len(self.memory_agent.memory.entries),
            experience_used=self.experience_used,
        )
        self._log_trace(final_trace)

        # Ensure complete trace is included in the output
        results["agent_evolution_trace"] = [t.to_dict() for t in self.agent_trace]
        results["agent_trace"] = results["agent_evolution_trace"]

        return results

    # ------------------------------------------------------------------
    # Verify-and-retry helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _arch_signature(arch: Any) -> str:
        """Structural signature to detect duplicate mutations."""
        try:
            parts = sorted(
                (str(c.name), str(c.type), int(c.quantity or 1), bool(c.managed))
                for c in arch.components
            )
            parts.append((_comm_of(arch), _deploy_of(arch)))
            return json.dumps(parts, sort_keys=True)
        except Exception:
            return str(getattr(arch, "name", "unknown"))

    @staticmethod
    def _weakest_dimension(cand: Candidate) -> str:
        scores = {
            "cost": cand.cost, "security": cand.security,
            "reliability": cand.reliability, "performance": cand.performance,
            "scalability": cand.scalability,
        }
        return min(scores, key=lambda k: scores[k])

    def _evaluate_record_mutation(
        self,
        mut: Any,
        parent_cand: Candidate,
        generation: int,
        structured_req: Any,
        raw_requirement: str,
        offspring_records: List[Dict[str, Any]],
        new_offspring_candidates: List[Candidate],
        seen_signatures: Set[str],
    ) -> Tuple[Optional[Candidate], float]:
        """Evaluate one mutation, compare with parent, store experience.

        Skips structurally duplicate architectures (logs a trace instead).
        Returns (child_candidate_or_None, fitness_delta).
        """
        sig = self._arch_signature(mut.new_architecture)
        if sig in seen_signatures:
            self._log_trace(AgentTraceEntry(
                agent="Multi-Objective Evaluator Agent",
                action="Skip Duplicate",
                architecture=mut.new_architecture.name,
                reason=f"Mutation reproduces an already-evaluated structure (parent: {parent_cand.architecture.name}); skipping re-evaluation.",
                outcome="skipped",
                fitness=parent_cand.overall_fitness,
                generation=generation,
                details={"modifications": list(mut.what_changed)},
            ))
            return None, 0.0
        seen_signatures.add(sig)

        # 7. Evaluation Agents (Evaluate offspring)
        child_cand, _, eval_trace = self.evaluator_agent.evaluate_candidate(
            mut.new_architecture,
            generation=generation,
            context=structured_req,
            application_type=self.application_type,
        )
        self._log_trace(eval_trace)

        # 8. Compare With Parent & Determine Success / Failure
        fitness_delta = child_cand.overall_fitness - parent_cand.overall_fitness
        mut.child_fitness = child_cand.overall_fitness
        mut.improvement_delta = fitness_delta
        # Harm gate: flag wins that crater a dimension (>10 pts) without paying
        # for it (overall gain < 1.5x the drop) so the caller retries with a
        # guard pattern (e.g. cost guard). Pure profitable trades pass through.
        mut.harmful_dim = None
        for _dim in ("cost", "security", "reliability", "performance", "scalability"):
            _drop = getattr(parent_cand, _dim, 0.0) - getattr(child_cand, _dim, 0.0)
            if _drop > 10.0 and fitness_delta < 1.5 * _drop:
                mut.harmful_dim = _dim
                break

        if fitness_delta > 0:
            outcome = "success"
            mut.outcome = "improved"
            reason = (
                f"{mut.triggering_agent}: {', '.join(mut.what_changed)} improved overall fitness from "
                f"{parent_cand.overall_fitness:.1f} to {child_cand.overall_fitness:.1f} (+{fitness_delta:.1f})."
            )
        elif fitness_delta < 0:
            outcome = "failure"
            mut.outcome = "degraded"
            reason = (
                f"{mut.triggering_agent}: {', '.join(mut.what_changed)} degraded overall fitness from "
                f"{parent_cand.overall_fitness:.1f} to {child_cand.overall_fitness:.1f} ({fitness_delta:.1f}) without sufficient benefit."
            )
        else:
            outcome = "failure"
            mut.outcome = "neutral"
            reason = (
                f"{mut.triggering_agent}: {', '.join(mut.what_changed)} produced neutral impact (fitness {child_cand.overall_fitness:.1f})."
            )

        # 9. Store Experience in Experience Memory Agent
        _, mem_trace = self.memory_agent.store_experience(
            architecture=child_cand.architecture.name,
            application_type=self.application_type,
            requirements=raw_requirement,
            generation=generation,
            evaluation_scores={
                "cost": child_cand.cost,
                "security": child_cand.security,
                "reliability": child_cand.reliability,
                "performance": child_cand.performance,
                "scalability": child_cand.scalability,
            },
            fitness=child_cand.overall_fitness,
            outcome=outcome,
            reason=reason,
            weaknesses=[
                f"low {k}"
                for k, v in [
                    ("cost", child_cand.cost),
                    ("security", child_cand.security),
                    ("reliability", child_cand.reliability),
                    ("performance", child_cand.performance),
                    ("scalability", child_cand.scalability),
                ]
                if v < 70
            ],
            changes_made=mut.what_changed,
            improvements=[f"+{fitness_delta:.1f} overall fitness"] if fitness_delta > 0 else [],
            experience_used=mut.experience_used,
        )
        self._log_trace(mem_trace)

        # Track experience strings for results
        for exp in mut.experience_used:
            if exp not in self.experience_used:
                self.experience_used.append(exp)

        new_offspring_candidates.append(child_cand)

        # Serialize offspring for generation history
        offspring_dict = self._candidate_to_dict(child_cand)
        offspring_dict["source_architecture"] = parent_cand.architecture.name
        offspring_dict["modifications"] = list(mut.what_changed)
        offspring_dict["what_changed"] = list(mut.what_changed)
        offspring_dict["reasoning"] = reason
        offspring_dict["why_it_changed"] = mut.why_it_changed
        offspring_dict["weakness_addressed"] = mut.weakness_addressed
        offspring_dict["source_weaknesses"] = [mut.weakness_addressed]
        offspring_dict["triggering_agent"] = mut.triggering_agent
        offspring_dict["experience_used"] = list(mut.experience_used)
        offspring_dict["outcome"] = mut.outcome
        offspring_dict["improvement_delta"] = round(fitness_delta, 2)
        offspring_records.append(offspring_dict)
        return child_cand, fitness_delta

    @staticmethod
    def _verification_trace(best: Candidate, baseline: Candidate) -> AgentTraceEntry:
        """End-of-run check: did every parameter move in the right direction?"""
        dims = ["cost", "security", "reliability", "performance", "scalability"]
        parts = []
        improved = 0
        for d in dims:
            b, f = getattr(baseline, d, 0.0), getattr(best, d, 0.0)
            arrow = "▲" if f > b else ("▼" if f < b else "•")
            if f > b:
                improved += 1
            parts.append(f"{d} {b:.1f}→{f:.1f} {arrow}")
        extras = getattr(best, "extra_scores", {}) or {}
        b_extras = getattr(baseline, "extra_scores", {}) or {}
        for k, f in extras.items():
            b = b_extras.get(k)
            if b is not None:
                arrow = "▲" if f > b else ("▼" if f < b else "•")
                if f > b:
                    improved += 1
                parts.append(f"{k} {b:.1f}→{f:.1f} {arrow}")
        total = len(dims) + len([k for k in extras if k in b_extras])
        overall_up = best.overall_fitness > baseline.overall_fitness
        return AgentTraceEntry(
            agent="Selection Agent",
            action="Verify Improvement",
            architecture=best.architecture.name,
            reason=f"End-of-run verification: {improved}/{total} parameters improved; overall {baseline.overall_fitness:.1f}→{best.overall_fitness:.1f}. " + "; ".join(parts),
            outcome="verified" if overall_up else "stagnated",
            fitness=best.overall_fitness,
            generation=getattr(best, "generation", 0),
            details={"improved_count": improved, "total_params": total},
        )

    @staticmethod
    def _candidate_to_dict(c: Candidate) -> Dict[str, Any]:
        arch = c.architecture
        return {
            "name": arch.name,
            "generation": c.generation,
            "fitness": round(c.overall_fitness, 2),
            "overall_grade": c.overall_grade,
            "objective_scores": {
                "cost": round(c.cost, 2),
                "security": round(c.security, 2),
                "reliability": round(c.reliability, 2),
                "performance": round(c.performance, 2),
                "scalability": round(c.scalability, 2),
            },
            "objective_grades": dict(getattr(c, "grades", {}) or {}),
            "score_breakdowns": {k: dict(v) for k, v in (getattr(c, "breakdowns", {}) or {}).items()},
            "weights_used": dict(getattr(c, "weights_used", {}) or {}),
            "weight_profile": getattr(c, "weight_profile", "default"),
            "domain_params": {
                k: {"score": float(v), "grade": (getattr(c, "extra_grades", {}) or {}).get(k, ""),
                    "breakdown": ((getattr(c, "extra_breakdowns", {}) or {}).get(k, {}))}
                for k, v in (getattr(c, "extra_scores", {}) or {}).items()
            },
            "selected": bool(getattr(c, "selected_for_mutation", False)),
            "components": [
                {
                    "name": comp.name,
                    "type": comp.type,
                    "quantity": comp.quantity,
                    "managed": comp.managed,
                }
                for comp in arch.components
            ],
            "services": list(arch.services),
            "communication_pattern": arch.communication_pattern,
            "deployment_strategy": arch.deployment_strategy,
        }
