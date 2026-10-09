from __future__ import annotations

from typing import Any, List

from ..models.architecture import Architecture
from .result import EvaluatorResult
from .scoring import ScoringContext, count_type, grade_for, has_type, smooth_benefit


def _components(architecture: Any) -> List[Any]:
    comps = getattr(architecture, "components", None)
    if isinstance(comps, list):
        return comps
    if isinstance(architecture, dict):
        comps = architecture.get("components", [])
        if isinstance(comps, list):
            return comps
    return []


class ReliabilityEvaluator:
    """Reliability evaluator (higher = survives failures without outage).

    Bottom-up rubric:
      - redundancy        /30  replica instances, scaled by availability target
      - data_durability   /25  managed DB + replicas + backup posture
      - fault_isolation   /25  decoupling (queue/cache) + bulkheads
      - recovery_ops      /20  deployment safety + elasticity signals
    """

    def evaluate(self, architecture: Architecture, context: Any = None) -> EvaluatorResult:
        ctx = context if isinstance(context, ScoringContext) else ScoringContext.from_any(context)
        comps = _components(architecture)
        total_instances = sum(max(1, int(getattr(c, "quantity", 1) or 1)) for c in comps)
        replicated = sum(1 for c in comps if int(getattr(c, "quantity", 1) or 1) > 1)
        # Higher availability targets demand more replicas for full marks.
        knee = 2.0 if ctx.availability_target < 99.9 else (3.5 if ctx.availability_target < 99.99 else 5.0)

        # --- 1. redundancy /30 ---
        redundancy = 30.0 * smooth_benefit(total_instances - 1, knee=knee)
        redundancy += min(4.0, replicated * 1.5)
        redundancy = min(30.0, redundancy)

        # --- 2. data durability /25 ---
        durability = 0.0
        dbs = [c for c in comps if str(getattr(c, "type", "")).lower() == "database"]
        if any(bool(getattr(c, "managed", False)) for c in dbs):
            durability += 9.0  # automated failover/backups/PITR signal
        if any(int(getattr(c, "quantity", 1) or 1) >= 2 for c in dbs):
            durability += 9.0  # synchronous replica / read replica
        elif dbs:
            durability += 3.0
        if has_type(comps, "datastore"):
            durability += 3.0
        if has_type(comps, "cache"):
            durability += 2.0  # cushions failover storms
        durability = min(25.0, durability)

        # --- 3. fault isolation /25 ---
        isolation = 0.0
        if has_type(comps, "messaging"):
            isolation += min(12.0, 8.0 + 2.0 * count_type(comps, "messaging"))
        if has_type(comps, "cache"):
            isolation += 5.0
        n_services = count_type(comps, "service", "application", "compute", "realtime")
        if n_services >= 3:
            isolation += 6.0  # bulkheads between failure domains
        elif n_services >= 1:
            isolation += 3.0
        comm = str(getattr(architecture, "communication_pattern", "sync") or "sync").lower()
        if comm in ("async", "event-driven"):
            isolation += 2.0
        isolation = min(25.0, isolation)

        # --- 4. recovery ops /20 ---
        deploy = str(getattr(architecture, "deployment_strategy", "standard") or "standard").lower()
        recovery = {"blue-green": 10.0, "canary": 10.0, "serverless": 8.0, "containerized": 7.0}.get(deploy, 3.0)
        if has_type(comps, "gateway", "load balancer"):
            recovery += 4.0  # health-checked routing / failover
        if any(bool(getattr(c, "managed", False)) for c in comps):
            recovery += 3.0
        if replicated:
            recovery += 3.0
        recovery = min(20.0, recovery)

        score = redundancy + durability + isolation + recovery
        breakdown = {
            "redundancy": round(redundancy, 2),
            "data_durability": round(durability, 2),
            "fault_isolation": round(isolation, 2),
            "recovery_ops": round(recovery, 2),
        }
        max_breakdown = {"redundancy": 30.0, "data_durability": 25.0, "fault_isolation": 25.0, "recovery_ops": 20.0}

        strengths, weaknesses = [], []
        if redundancy >= 20:
            strengths.append(f"{total_instances} instances across {replicated} replicated component(s) remove single points of failure.")
        else:
            weaknesses.append(f"Only {total_instances} instance(s); a single node failure risks outage (target {ctx.availability_target}%).")
        if durability >= 15:
            strengths.append("Durable data tier (managed + replicated) with failover/backups.")
        else:
            weaknesses.append("Fragile data tier: needs managed failover and at least one DB replica.")
        if isolation >= 15:
            strengths.append("Decoupled async/cache paths enable graceful degradation.")
        else:
            weaknesses.append("Tight synchronous coupling lacks backpressure buffering.")
        if recovery >= 12:
            strengths.append(f"Safe delivery posture ({deploy}) with health-checked routing.")
        else:
            weaknesses.append(f"Deployment '{deploy}' offers limited zero-downtime / rollback safety.")
        if not strengths:
            strengths.append("Baseline availability for non-critical workloads.")
        if not weaknesses and score < 70:
            weaknesses.append("Lacks multi-AZ, chaos-tested recovery and automated circuit breaking.")

        reason = (
            f"Reliability {score:.1f}/100 [target {ctx.availability_target}%]: redundancy {redundancy:.0f}/30, "
            f"durability {durability:.0f}/25, isolation {isolation:.0f}/25, recovery {recovery:.0f}/20."
        )
        return EvaluatorResult(score, reasoning=reason, strengths=strengths, weaknesses=weaknesses,
                               breakdown=breakdown, max_breakdown=max_breakdown)
