from __future__ import annotations

from typing import Any, List

from ..models.architecture import Architecture
from .result import EvaluatorResult
from .scoring import (
    DimensionScore,
    ScoringContext,
    clamp01,
    count_type,
    estimate_monthly_cost,
    grade_for,
    has_type,
    smooth_benefit,
)


def _components(architecture: Any) -> List[Any]:
    comps = getattr(architecture, "components", None)
    if isinstance(comps, list):
        return comps
    if isinstance(architecture, dict):
        comps = architecture.get("components", [])
        if isinstance(comps, list):
            return comps
    return []


class CostEvaluator:
    """Cost-efficiency evaluator (higher = cheaper / better value).

    Bottom-up rubric (earns up to 100, rarely saturates):
      - right_sizing      /35  component count vs. scale tier
      - budget_fit        /30  estimated monthly cost vs. budget (or $/user curve)
      - ops_efficiency    /20  managed/self-hosted balance, serverless fit
      - elasticity_value  /15  extra spend buys caching/buffering/scale
    """

    IDEAL_COUNT = {"small": (3, 5), "medium": (4, 7), "large": (6, 10), "hyperscale": (8, 14)}
    TARGET_CPU = {"small": 0.60, "medium": 0.35, "large": 0.18, "hyperscale": 0.10}  # $/user/mo

    def evaluate(self, architecture: Architecture, context: Any = None) -> EvaluatorResult:
        ctx = context if isinstance(context, ScoringContext) else ScoringContext.from_any(context)
        comps = _components(architecture)
        n = len(comps)
        tier = ctx.scale_tier
        lo, hi = self.IDEAL_COUNT[tier]

        # --- 1. right sizing /35 ---
        if lo <= n <= hi:
            right = 35.0
        elif n < lo:
            # Under-provisioned for the tier (missing tiers/layers).
            right = 35.0 * (0.55 + 0.45 * clamp01(n / max(lo, 1)))
        else:
            over = n - hi
            right = 35.0 * (2.718 ** (-over / 3.0))

        # --- 2. budget fit /30 ---
        est = estimate_monthly_cost(comps)
        if ctx.max_monthly_cost:
            import math as _m

            ratio = est / max(float(ctx.max_monthly_cost), 1.0)
            budget = 30.0 / (1.0 + _m.exp((ratio - 0.75) / 0.15))
        else:
            users = max(ctx.expected_users, 100)
            cpu = est / users
            target = self.TARGET_CPU[tier]
            budget = 30.0 / (1.0 + (cpu / target) ** 1.2)

        # --- 3. ops efficiency /20 ---
        managed = sum(1 for c in comps if bool(getattr(c, "managed", False)))
        ratio_m = (managed / n) if n else 0.0
        # Ideal managed ratio ~0.45; both extremes lose points (vendor premium vs ops burden).
        balance = 1.0 - min(1.0, abs(ratio_m - 0.45) / 0.55)
        ops = 14.0 * (0.35 + 0.65 * balance)
        comm = str(getattr(architecture, "communication_pattern", "sync") or "sync").lower()
        deploy = str(getattr(architecture, "deployment_strategy", "standard") or "standard").lower()
        if deploy == "serverless" and n <= 8:
            ops += 4.0  # pay-per-use fits variable/small workloads
        elif deploy in ("containerized", "blue-green", "canary") and tier in ("large", "hyperscale"):
            ops += 3.0  # automation pays off at scale
        if has_type(comps, "cdn") and ctx.latency_sla_ms <= 150:
            ops += 1.0
        ops = min(20.0, ops)

        # --- 4. elasticity value /15 ---
        useful = count_type(comps, "messaging") + count_type(comps, "cache") + count_type(comps, "cdn")
        elastic = 15.0 * smooth_benefit(useful, knee=2.0)
        if ctx.cost_sensitive and n > hi:
            elastic *= 0.7  # oversized + cost-sensitive: spend is not justified

        score = right + budget + ops + elastic
        breakdown = {
            "right_sizing": round(right, 2),
            "budget_fit": round(budget, 2),
            "ops_efficiency": round(ops, 2),
            "elasticity_value": round(elastic, 2),
        }
        max_breakdown = {"right_sizing": 35.0, "budget_fit": 30.0, "ops_efficiency": 20.0, "elasticity_value": 15.0}

        strengths, weaknesses = [], []
        if right >= 28:
            strengths.append(f"Component count ({n}) fits the {tier} tier ({lo}-{hi} ideal). Est. ${est:,.0f}/mo.")
        elif n > hi:
            weaknesses.append(f"{n} components exceed the {tier}-tier ideal ({lo}-{hi}); est. ${est:,.0f}/mo inflates cost.")
        else:
            weaknesses.append(f"Only {n} components for {tier} scale may under-provision required tiers.")
        if ctx.max_monthly_cost:
            if est <= ctx.max_monthly_cost:
                strengths.append(f"Est. ${est:,.0f}/mo fits the ${ctx.max_monthly_cost:,.0f} budget.")
            else:
                weaknesses.append(f"Est. ${est:,.0f}/mo exceeds the ${ctx.max_monthly_cost:,.0f} budget.")
        else:
            users = max(ctx.expected_users, 100)
            strengths.append(f"Est. ${est:,.0f}/mo = ${est / users:.2f}/user for {ctx.expected_users:,} users.")
            if budget < 15:
                weaknesses.append(f"Cost per user (${est / users:.2f}) is high for {tier} scale.")
        if ratio_m > 0.75:
            weaknesses.append(f"{managed}/{n} managed services add vendor premium; consider self-hosting non-critical tiers.")
        elif ratio_m < 0.2 and n > 5:
            weaknesses.append("Mostly self-hosted at this size implies significant ops burden (not free).")
        else:
            strengths.append(f"Balanced managed ratio ({managed}/{n}) limits both premium and ops burden.")
        if elastic >= 10:
            strengths.append("Spend buys elastic capacity (cache/queue/CDN) rather than idle overhead.")
        if not strengths:
            strengths.append("Baseline cost posture with no extreme overspend.")
        if not weaknesses and score < 70:
            weaknesses.append("Moderate infrastructure spend without a clear budget anchor.")

        reason = (
            f"Cost {score:.1f}/100 [{ctx.scale_tier}, {ctx.expected_users:,} users]: "
            f"sizing {right:.0f}/35, budget {budget:.0f}/30, ops {ops:.0f}/20, value {elastic:.0f}/15 "
            f"(est. ${est:,.0f}/mo)."
        )
        return EvaluatorResult(score, reasoning=reason, strengths=strengths, weaknesses=weaknesses,
                               breakdown=breakdown, max_breakdown=max_breakdown)
