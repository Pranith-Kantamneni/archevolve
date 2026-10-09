from __future__ import annotations

from typing import Any, List

from ..models.architecture import Architecture
from .result import EvaluatorResult
from .scoring import ScoringContext, count_type, grade_for, has_name_like, has_type, smooth_benefit


def _components(architecture: Any) -> List[Any]:
    comps = getattr(architecture, "components", None)
    if isinstance(comps, list):
        return comps
    if isinstance(architecture, dict):
        comps = architecture.get("components", [])
        if isinstance(comps, list):
            return comps
    return []


class PerformanceEvaluator:
    """Latency/throughput evaluator (higher = faster under required load).

    Bottom-up rubric:
      - caching           /30  cache + CDN, weighted by latency SLA strictness
      - communication     /25  async/event-driven bonus minus hop penalty
      - data_path         /25  read replicas + managed tuning + non-blocking buffer
      - concurrency       /20  instance headroom vs. expected users
    """

    def evaluate(self, architecture: Architecture, context: Any = None) -> EvaluatorResult:
        ctx = context if isinstance(context, ScoringContext) else ScoringContext.from_any(context)
        comps = _components(architecture)
        sla = ctx.latency_sla_ms
        strict_sla = sla <= 100

        # --- 1. caching /30 ---
        caching = 0.0
        n_cache = count_type(comps, "cache")
        if n_cache:
            caching += min(18.0, 12.0 + 4.0 * n_cache)
        if has_type(comps, "cdn") or has_name_like(comps, "cdn", "edge", "cloudfront"):
            caching += 12.0 if strict_sla else 7.0
        elif strict_sla:
            caching += 0.0  # strict SLA with no edge layer earns nothing here
        caching = min(30.0, caching)

        # --- 2. communication /25 ---
        comm = str(getattr(architecture, "communication_pattern", "sync") or "sync").lower()
        base = {"event-driven": 20.0, "async": 17.0}.get(comm, 10.0)
        n_services = count_type(comps, "service", "application", "compute", "realtime")
        # Each extra hop adds serialization latency: smooth penalty, not a cliff.
        hop_penalty = 10.0 * smooth_benefit(max(0, n_services - 4), knee=4.0)
        if has_type(comps, "gateway"):
            base += 2.0  # SSL termination / compression / routing
        communication = max(0.0, min(25.0, base - hop_penalty + (2.0 if comm != "sync" and has_type(comps, "messaging") else 0.0)))

        # --- 3. data path /25 ---
        data = 0.0
        dbs = [c for c in comps if str(getattr(c, "type", "")).lower() == "database"]
        if any(int(getattr(c, "quantity", 1) or 1) >= 2 for c in dbs):
            data += 11.0  # read scaling
        elif dbs:
            data += 4.0
        if any(bool(getattr(c, "managed", False)) for c in dbs):
            data += 4.0
        if has_type(comps, "messaging"):
            data += 6.0  # non-blocking writes
        if has_type(comps, "datastore"):
            data += 4.0
        data = min(25.0, data)

        # --- 4. concurrency headroom /20 ---
        total_instances = sum(max(1, int(getattr(c, "quantity", 1) or 1)) for c in comps)
        users = max(ctx.expected_users, 100)
        # Rough capacity model: each instance ~1.5k concurrent users of headroom.
        headroom_ratio = (total_instances * 1500) / users
        concurrency = 20.0 * (1.0 - 2.718 ** (-max(headroom_ratio, 0.0) / 1.2))
        if has_type(comps, "messaging"):
            concurrency = min(20.0, concurrency + 2.0)

        score = caching + communication + data + concurrency
        breakdown = {
            "caching": round(caching, 2),
            "communication": round(communication, 2),
            "data_path": round(data, 2),
            "concurrency": round(concurrency, 2),
        }
        max_breakdown = {"caching": 30.0, "communication": 25.0, "data_path": 25.0, "concurrency": 20.0}

        strengths, weaknesses = [], []
        if caching >= 18:
            strengths.append("Hot-path caching (+edge) absorbs repeated reads.")
        else:
            msg = "No cache forces repeated DB/disk I/O"
            msg += f"; sub-{sla:.0f}ms SLA needs edge caching" if strict_sla else ""
            weaknesses.append(msg + ".")
        if comm in ("async", "event-driven"):
            strengths.append(f"{comm.title()} pipeline avoids request-thread blocking.")
        else:
            weaknesses.append("Synchronous chaining adds cascade latency under load.")
        if data >= 14:
            strengths.append("Read-scaled data path with non-blocking writes.")
        else:
            weaknesses.append("Single-writer data path will bottleneck reads/writes.")
        if concurrency >= 13:
            strengths.append(f"{total_instances} instances give headroom for {ctx.expected_users:,} users.")
        else:
            weaknesses.append(f"{total_instances} instance(s) look thin for {ctx.expected_users:,} users.")
        if not strengths:
            strengths.append("Standard request pipeline latency.")
        if not weaknesses and score < 70:
            weaknesses.append("Cross-service serialization still adds overhead at p99.")

        reason = (
            f"Performance {score:.1f}/100 [SLA {sla:.0f}ms, {ctx.expected_users:,} users]: "
            f"cache {caching:.0f}/30, comm {communication:.0f}/25, data {data:.0f}/25, headroom {concurrency:.0f}/20."
        )
        return EvaluatorResult(score, reasoning=reason, strengths=strengths, weaknesses=weaknesses,
                               breakdown=breakdown, max_breakdown=max_breakdown)
