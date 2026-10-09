from __future__ import annotations

from typing import Any, List

from ..models.architecture import Architecture
from .result import EvaluatorResult
from .scoring import ScoringContext, clamp01, count_type, grade_for, has_name_like, has_type


def _components(architecture: Any) -> List[Any]:
    comps = getattr(architecture, "components", None)
    if isinstance(comps, list):
        return comps
    if isinstance(architecture, dict):
        comps = architecture.get("components", [])
        if isinstance(comps, list):
            return comps
    return []


class SecurityEvaluator:
    """Security-posture evaluator (higher = stronger defense in depth).

    Bottom-up rubric:
      - perimeter           /25  gateway + WAF/security layer + LB
      - identity            /25  auth enforcement (dedicated > gateway-only > none)
      - data_protection     /30  vault/KMS + managed-DB encryption + audit/compliance
      - segmentation        /20  decoupled async paths + minimal public entry points
    Thresholds tighten when security_level == high or compliance is required.
    """

    def evaluate(self, architecture: Architecture, context: Any = None) -> EvaluatorResult:
        ctx = context if isinstance(context, ScoringContext) else ScoringContext.from_any(context)
        comps = _components(architecture)
        strict = ctx.security_level == "high" or bool(ctx.compliance)

        # --- 1. perimeter /25 ---
        perimeter = 0.0
        if has_type(comps, "gateway"):
            perimeter += 10.0
        if has_type(comps, "security"):
            # Partial credit scales with number of distinct security controls.
            perimeter += min(12.0, 6.0 + 3.0 * count_type(comps, "security"))
            if has_name_like(comps, "waf", "firewall"):
                perimeter += 3.0
        if has_name_like(comps, "load balancer"):
            perimeter += 2.0
        perimeter = min(25.0, perimeter)

        # --- 2. identity /25 ---
        identity = 0.0
        dedicated_auth = has_name_like(comps, "auth", "identity", "cognito", "keycloak", "okta")
        if dedicated_auth:
            identity += 15.0
        if has_type(comps, "gateway"):
            identity += 8.0
        if has_type(comps, "security") and has_name_like(comps, "vault", "kms", "secrets"):
            identity += 2.0
        if identity == 0 and len(comps) <= 3:
            identity = 4.0  # tiny closed surface, weak but not fully exposed
        identity = min(25.0, identity)

        # --- 3. data protection /30 ---
        data = 0.0
        if has_name_like(comps, "vault", "kms", "hsm", "secrets"):
            data += 12.0
        managed_db = any(str(getattr(c, "type", "")).lower() == "database" and bool(getattr(c, "managed", False)) for c in comps)
        if managed_db:
            data += 7.0  # encryption at rest + automated patching signal
        if has_name_like(comps, "audit"):
            data += 7.0 if strict else 5.0
        elif strict:
            data += 0.0  # strict mode: no audit logger, no credit
        else:
            data += 2.0
        if ctx.authentication_required and dedicated_auth:
            data += 2.0
        if has_name_like(comps, "backup", "recovery"):
            data += 2.0
        data = min(30.0, data)

        # --- 4. segmentation /20 ---
        seg = 0.0
        comm = str(getattr(architecture, "communication_pattern", "sync") or "sync").lower()
        if comm == "event-driven":
            seg += 9.0
        elif comm == "async":
            seg += 7.0
        else:
            seg += 3.0
        if has_type(comps, "messaging"):
            seg += min(5.0, 3.0 + count_type(comps, "messaging"))
        entry = count_type(comps, "gateway", "load balancer")
        n = len(comps)
        if n:
            # Fewer public entry points per service = smaller blast radius.
            seg += 6.0 * clamp01(1.6 - (entry / max(n, 1)) * 2.2 + 0.6) if entry else 1.0
        seg = min(20.0, seg)

        score = perimeter + identity + data + seg
        breakdown = {
            "perimeter": round(perimeter, 2),
            "identity": round(identity, 2),
            "data_protection": round(data, 2),
            "segmentation": round(seg, 2),
        }
        max_breakdown = {"perimeter": 25.0, "identity": 25.0, "data_protection": 30.0, "segmentation": 20.0}

        strengths, weaknesses = [], []
        if perimeter >= 18:
            strengths.append("Layered edge controls (gateway + dedicated security controls).")
        else:
            weaknesses.append("Thin edge perimeter: add an API gateway and WAF/secrets controls.")
        if dedicated_auth:
            strengths.append("Dedicated authentication/identity enforcement present.")
        elif has_type(comps, "gateway"):
            weaknesses.append("No dedicated auth service; gateway-only auth is partial.")
        else:
            weaknesses.append("No explicit authentication component found.")
        if data >= 20:
            strengths.append("Data-protection controls (vault/KMS, managed encryption, audit) present.")
        else:
            missing = []
            if not has_name_like(comps, "vault", "kms", "secrets"):
                missing.append("secrets management")
            if strict and not has_name_like(comps, "audit"):
                missing.append("audit logging (required for compliance)")
            weaknesses.append("Weak data-protection posture: missing " + (", ".join(missing) or "defense depth") + ".")
        if seg >= 13:
            strengths.append("Decoupled async paths limit lateral blast radius.")
        elif comm == "sync" and not has_type(comps, "messaging"):
            weaknesses.append("Synchronous-only coupling widens the exploit blast radius.")
        if not strengths:
            strengths.append("Baseline isolation suitable for low-risk workloads.")
        if not weaknesses and score < 70:
            weaknesses.append("Lacks advanced controls (per-request authz, mTLS, anomaly detection).")

        req_tag = "strict" if strict else ctx.security_level
        reason = (
            f"Security {score:.1f}/100 [{req_tag}]: perimeter {perimeter:.0f}/25, "
            f"identity {identity:.0f}/25, data {data:.0f}/30, segmentation {seg:.0f}/20."
        )
        return EvaluatorResult(score, reasoning=reason, strengths=strengths, weaknesses=weaknesses,
                               breakdown=breakdown, max_breakdown=max_breakdown)
