from __future__ import annotations

from typing import Any, List

from ..models.architecture import Architecture
from .result import EvaluatorResult
from .scoring import ScoringContext, count_type, grade_for, has_type


def _components(architecture: Any) -> List[Any]:
    comps = getattr(architecture, "components", None)
    if isinstance(comps, list):
        return comps
    if isinstance(architecture, dict):
        comps = architecture.get("components", [])
        if isinstance(comps, list):
            return comps
    return []


class ScalabilityEvaluator:
    """Elastic-scalability evaluator (higher = grows with demand).

    Bottom-up rubric:
      - horizontal        /30  independently scalable services + scalable deploy
      - buffering         /25  queue/event-bus absorbs surges (graded by depth)
      - data_scaling      /25  cache + replicas + sharded stores/CDN
      - automation        /20  managed elasticity + load distribution
    """

    def evaluate(self, architecture: Architecture, context: Any = None) -> EvaluatorResult:
        ctx = context if isinstance(context, ScoringContext) else ScoringContext.from_any(context)
        comps = _components(architecture)
        n_services = count_type(comps, "service", "application", "compute", "realtime")
        deploy = str(getattr(architecture, "deployment_strategy", "standard") or "standard").lower()

        # --- 1. horizontal /30 ---
        horizontal = 0.0
        if n_services >= 6:
            horizontal += 14.0
        elif n_services >= 3:
            horizontal += 10.0
        elif n_services >= 1:
            horizontal += 5.0
        horizontal += {"serverless": 14.0, "containerized": 11.0, "blue-green": 8.0, "canary": 8.0}.get(deploy, 3.0)
        if n_services <= 1 and deploy == "standard":
            horizontal = min(horizontal, 8.0)  # monolith on fixed hosts barely scales
        horizontal = min(30.0, horizontal)

        # --- 2. buffering /25 ---
        n_q = count_type(comps, "messaging")
        comm = str(getattr(architecture, "communication_pattern", "sync") or "sync").lower()
        if n_q >= 2 or (n_q >= 1 and comm == "event-driven"):
            buffering = 25.0 if n_q >= 2 else 22.0
        elif n_q == 1:
            buffering = 17.0
        else:
            buffering = 4.0 if comm in ("async", "event-driven") else 2.0

        # --- 3. data scaling /25 ---
        data = 0.0
        if has_type(comps, "cache"):
            data += 8.0
        dbs = [c for c in comps if str(getattr(c, "type", "")).lower() == "database"]
        if any(int(getattr(c, "quantity", 1) or 1) >= 2 for c in dbs):
            data += 9.0
        elif dbs:
            data += 3.0
        if has_type(comps, "datastore"):
            data += 5.0
        if has_type(comps, "cdn"):
            data += 3.0
        data = min(25.0, data)

        # --- 4. automation /20 ---
        managed = sum(1 for c in comps if bool(getattr(c, "managed", False)))
        automation = 0.0
        if deploy in ("serverless", "containerized"):
            automation += 8.0
        elif deploy in ("blue-green", "canary"):
            automation += 6.0
        else:
            automation += 2.0
        if has_type(comps, "gateway", "load balancer"):
            automation += 5.0
        if comps:
            automation += 7.0 * (managed / len(comps))
        automation = min(20.0, automation)

        score = horizontal + buffering + data + automation
        breakdown = {
            "horizontal": round(horizontal, 2),
            "buffering": round(buffering, 2),
            "data_scaling": round(data, 2),
            "automation": round(automation, 2),
        }
        max_breakdown = {"horizontal": 30.0, "buffering": 25.0, "data_scaling": 25.0, "automation": 20.0}

        strengths, weaknesses = [], []
        if horizontal >= 20:
            strengths.append(f"{n_services} independently scalable service(s) on {deploy} substrate.")
        else:
            weaknesses.append("Monolithic/fixed deployment restricts horizontal elasticity.")
        if buffering >= 17:
            strengths.append("Event/queue buffering absorbs traffic surges elastically.")
        else:
            weaknesses.append("No message buffer: synchronous fan-out caps concurrency under spikes.")
        if data >= 15:
            strengths.append("Data tier scales (replicas/cache/sharded stores).")
        else:
            weaknesses.append("Single-writer data tier will bottleneck horizontal growth.")
        if automation >= 12:
            strengths.append("Managed/automated elasticity (autoscale + load distribution).")
        else:
            weaknesses.append("Manual scaling with limited load distribution.")
        if not strengths:
            strengths.append("Baseline single-node scaling capacity.")
        if not weaknesses and score < 70:
            weaknesses.append("Lacks sharded/partitioned data tier for very large growth.")

        reason = (
            f"Scalability {score:.1f}/100 [{ctx.scale_tier}, {ctx.expected_users:,} users]: "
            f"horizontal {horizontal:.0f}/30, buffering {buffering:.0f}/25, data {data:.0f}/25, automation {automation:.0f}/20."
        )
        return EvaluatorResult(score, reasoning=reason, strengths=strengths, weaknesses=weaknesses,
                               breakdown=breakdown, max_breakdown=max_breakdown)
