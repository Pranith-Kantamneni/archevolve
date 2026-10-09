"""Domain-specific quality parameters for ARCHEVOLVE.

Beyond the 5 universal dimensions (cost, security, reliability, performance,
scalability), real systems are judged on parameters that only make sense for
their domain: a bank lives or dies by auditability and transactional
consistency, a chat app by realtime delivery, an IoT platform by ingestion
scale.  This module defines those parameters as small, bottom-up,
requirement-aware evaluators.

Blending rule (see :func:`blend_overall`):
    overall = (1 - EXTRA_SHARE) * core_weighted + EXTRA_SHARE * mean(extras)

with ``EXTRA_SHARE = 0.20``.  Domains without extra params keep pure core
scoring, so default behavior is unchanged.

To add a new domain parameter:
  1. Write ``evaluate_<name>(components, arch, ctx) -> DimensionScore``.
  2. Register it in ``PARAM_DEFS`` and attach it to domains in ``DOMAIN_PARAMS``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from .scoring import (
    DimensionScore,
    ScoringContext,
    clamp01,
    count_type,
    has_name_like,
    has_type,
    smooth_benefit,
)

EXTRA_SHARE = 0.20


def _comps(arch: Any) -> List[Any]:
    comps = getattr(arch, "components", None)
    if isinstance(comps, list):
        return comps
    if isinstance(arch, dict) and isinstance(arch.get("components"), list):
        return arch["components"]
    return []


def _comm(arch: Any) -> str:
    if isinstance(arch, dict):
        return str(arch.get("communication_pattern", "sync") or "sync").lower()
    return str(getattr(arch, "communication_pattern", "sync") or "sync").lower()


def _deploy(arch: Any) -> str:
    if isinstance(arch, dict):
        return str(arch.get("deployment_strategy", "standard") or "standard").lower()
    return str(getattr(arch, "deployment_strategy", "standard") or "standard").lower()


def _instances(comps: List[Any]) -> int:
    return sum(max(1, int(getattr(c, "quantity", 1) or 1)) for c in comps)


# ---------------------------------------------------------------------------
# Parameter evaluators (each 0-100, earned bottom-up)
# ---------------------------------------------------------------------------


def evaluate_compliance_governance(comps: List[Any], arch: Any, ctx: ScoringContext) -> DimensionScore:
    """Auditability & regulatory control (banking, finance, healthcare).

    Deliberately hard to max out: full marks need a compliance-named audit
    trail (e.g. "Audit Logger (pci-dss)"), a secrets vault, a managed
    encrypted datastore, layered edge controls AND an audit event bus.
    Generated baselines land in the 60s-70s; evolution earns the rest.
    """
    audit = 0.0
    required = [c.lower() for c in (ctx.compliance or [])]
    names = " ".join(str(getattr(c, "name", "")).lower() for c in comps)
    if has_name_like(comps, "audit"):
        audit += 15.0
    if required and any(r in names for r in required):
        audit += 10.0
    elif not required and has_name_like(comps, "audit"):
        audit += 10.0
    if has_type(comps, "messaging"):
        audit += 7.0  # tamper-evident audit event bus
    if count_type(comps, "security") >= 3:
        audit += 3.0  # defense-in-depth governance footprint
    audit = min(35.0, audit)

    secrets = 0.0
    if has_name_like(comps, "vault", "kms", "hsm", "secrets"):
        secrets += 20.0
    if any(str(getattr(c, "type", "")).lower() in ("database", "datastore") and bool(getattr(c, "managed", False)) for c in comps):
        secrets += 6.0
    if any(str(getattr(c, "type", "")).lower() == "database" and int(getattr(c, "quantity", 1) or 1) >= 2 for c in comps):
        secrets += 4.0  # replicated encrypted store, no single copy of record
    secrets = min(30.0, secrets)

    privilege = 0.0
    if has_type(comps, "gateway"):
        privilege += 8.0
    if has_name_like(comps, "waf", "firewall"):
        privilege += 6.0
    if count_type(comps, "security") >= 3:
        privilege += 6.0
    privilege = min(20.0, privilege)

    retention = 0.0
    if has_type(comps, "database", "datastore"):
        retention += 6.0
    if has_type(comps, "messaging"):
        retention += 7.0  # immutable audit bus
    if has_name_like(comps, "backup", "vault"):
        retention += 2.0
    retention = min(15.0, retention)

    score = audit + secrets + privilege + retention
    strengths, weaknesses = [], []
    if audit >= 25:
        strengths.append("Explicit audit-logging trail for regulator review.")
    else:
        weaknesses.append("No audit logger: compliance reviews and forensics will fail" + (" (" + ", ".join(ctx.compliance) + " required)" if ctx.compliance else "") + ".")
    if secrets >= 20:
        strengths.append("Centralized secrets/encryption-key governance.")
    else:
        weaknesses.append("Missing secrets vault / managed key lifecycle.")
    if not strengths:
        strengths.append("Baseline governance posture.")
    return DimensionScore(score, breakdown={"audit_trail": round(audit, 2), "secrets_governance": round(secrets, 2), "least_privilege": round(privilege, 2), "retention": round(retention, 2)},
                          max_breakdown={"audit_trail": 35.0, "secrets_governance": 30.0, "least_privilege": 20.0, "retention": 15.0},
                          strengths=strengths, weaknesses=weaknesses,
                          reason=f"Compliance {score:.1f}/100: audit {audit:.0f}/35, secrets {secrets:.0f}/30, privilege {privilege:.0f}/20, retention {retention:.0f}/15.")


def evaluate_transactional_consistency(comps: List[Any], arch: Any, ctx: ScoringContext) -> DimensionScore:
    """Exactly-once / ACID transfer semantics (banking, finance, e-commerce)."""
    durable = 0.0
    dbs = [c for c in comps if str(getattr(c, "type", "")).lower() == "database"]
    if dbs:
        durable += 15.0
    if any(bool(getattr(c, "managed", False)) for c in dbs):
        durable += 10.0
    if any(int(getattr(c, "quantity", 1) or 1) >= 2 for c in dbs):
        durable += 10.0
    durable = min(35.0, durable)

    outbox = 0.0
    if has_type(comps, "messaging"):
        outbox += min(20.0, 12.0 + 4.0 * count_type(comps, "messaging"))
    if _comm(arch) in ("async", "event-driven"):
        outbox += 10.0
    outbox = min(30.0, outbox)

    discipline = 20.0 if len(dbs) <= 2 else max(4.0, 20.0 - (len(dbs) - 2) * 6.0)

    saga = 0.0
    if count_type(comps, "service", "application", "compute") >= 2:
        saga += 10.0  # saga/choreography bulkheads
    if has_type(comps, "gateway"):
        saga += 5.0
    saga = min(15.0, saga)

    score = durable + outbox + discipline + saga
    strengths, weaknesses = [], []
    if durable >= 25:
        strengths.append("Durable replicated relational core for money movements.")
    else:
        weaknesses.append("No replicated durable database: transfers risk loss/duplication.")
    if outbox >= 18:
        strengths.append("Outbox/event pattern decouples settlement steps safely.")
    else:
        weaknesses.append("Synchronous settlement without an outbox/queue risks partial commits.")
    if not strengths:
        strengths.append("Baseline consistency posture.")
    return DimensionScore(score, breakdown={"durable_core": round(durable, 2), "outbox_events": round(outbox, 2), "writer_discipline": round(discipline, 2), "saga_bulkheads": round(saga, 2)},
                          max_breakdown={"durable_core": 35.0, "outbox_events": 30.0, "writer_discipline": 20.0, "saga_bulkheads": 15.0},
                          strengths=strengths, weaknesses=weaknesses,
                          reason=f"Consistency {score:.1f}/100: durable {durable:.0f}/35, outbox {outbox:.0f}/30, discipline {discipline:.0f}/20, saga {saga:.0f}/15.")


def evaluate_realtime_delivery(comps: List[Any], arch: Any, ctx: ScoringContext) -> DimensionScore:
    """Sub-second push delivery & presence (chat, gaming, ride-sharing)."""
    edge = 0.0
    if has_type(comps, "realtime"):
        edge += 20.0
    if has_name_like(comps, "websocket", "socket", "presence", "realtime", "dispatch"):
        edge += 15.0
    edge = min(35.0, edge)

    fabric = 0.0
    if has_type(comps, "messaging"):
        fabric += 15.0
    if _comm(arch) == "event-driven":
        fabric += 10.0
    elif _comm(arch) == "async":
        fabric += 7.0
    fabric = min(25.0, fabric)

    presence = 0.0
    if has_type(comps, "cache"):
        presence += 12.0
    if has_name_like(comps, "presence"):
        presence += 8.0
    presence = min(20.0, presence)

    path = 0.0
    if has_type(comps, "gateway", "load balancer"):
        path += 8.0
    if has_type(comps, "cdn") and ctx.latency_sla_ms <= 150:
        path += 12.0
    elif has_type(comps, "cdn"):
        path += 6.0
    path = min(20.0, path)

    score = edge + fabric + presence + path
    strengths, weaknesses = [], []
    if edge >= 20:
        strengths.append("Dedicated realtime edge (socket/presence/dispatch hub).")
    else:
        weaknesses.append("No realtime push hub: polling will breach delivery SLAs.")
    if fabric >= 15:
        strengths.append("Event fabric fans out messages without blocking.")
    else:
        weaknesses.append("Request-response only: no fan-out fabric for live updates.")
    if not strengths:
        strengths.append("Baseline delivery posture.")
    return DimensionScore(score, breakdown={"realtime_edge": round(edge, 2), "push_fabric": round(fabric, 2), "presence_state": round(presence, 2), "low_latency_path": round(path, 2)},
                          max_breakdown={"realtime_edge": 35.0, "push_fabric": 25.0, "presence_state": 20.0, "low_latency_path": 20.0},
                          strengths=strengths, weaknesses=weaknesses,
                          reason=f"Realtime {score:.1f}/100 [SLA {ctx.latency_sla_ms:.0f}ms]: edge {edge:.0f}/35, fabric {fabric:.0f}/25, presence {presence:.0f}/20, path {path:.0f}/20.")


def evaluate_elastic_burst(comps: List[Any], arch: Any, ctx: ScoringContext) -> DimensionScore:
    """Flash-sale / viral-spike absorption (e-commerce, social, streaming...)."""
    n_q = count_type(comps, "messaging")
    buffer = min(30.0, 20.0 + 5.0 * n_q) if n_q else 4.0

    stateless = 0.0
    n_svc = count_type(comps, "service", "application", "compute", "realtime")
    stateless += 15.0 if n_svc >= 4 else (10.0 if n_svc >= 2 else 4.0)
    stateless += {"serverless": 15.0, "containerized": 12.0, "blue-green": 8.0, "canary": 8.0}.get(_deploy(arch), 3.0)
    stateless = min(30.0, stateless)

    offload = 0.0
    if has_type(comps, "cache"):
        offload += 12.0
    if has_type(comps, "cdn"):
        offload += 8.0
    offload = min(20.0, offload)

    traffic = 0.0
    if has_type(comps, "gateway", "load balancer"):
        traffic += 12.0
    managed_ratio = (sum(1 for c in comps if bool(getattr(c, "managed", False))) / len(comps)) if comps else 0.0
    traffic += 8.0 * clamp01(managed_ratio / 0.4)
    traffic = min(20.0, traffic)

    score = buffer + stateless + offload + traffic
    strengths, weaknesses = [], []
    if buffer >= 20:
        strengths.append(f"Queue buffering absorbs {ctx.expected_users:,}-user spikes.")
    else:
        weaknesses.append("No surge buffer: traffic spikes will cascade into outages.")
    if stateless >= 20:
        strengths.append("Stateless tiers scale out on elastic substrate.")
    else:
        weaknesses.append("Stateful/fixed tiers cannot burst horizontally.")
    if not strengths:
        strengths.append("Baseline burst posture.")
    return DimensionScore(score, breakdown={"surge_buffer": round(buffer, 2), "stateless_scale": round(stateless, 2), "read_offload": round(offload, 2), "traffic_mgmt": round(traffic, 2)},
                          max_breakdown={"surge_buffer": 30.0, "stateless_scale": 30.0, "read_offload": 20.0, "traffic_mgmt": 20.0},
                          strengths=strengths, weaknesses=weaknesses,
                          reason=f"Burst {score:.1f}/100 [{ctx.expected_users:,} users]: buffer {buffer:.0f}/30, stateless {stateless:.0f}/30, offload {offload:.0f}/20, traffic {traffic:.0f}/20.")


def evaluate_media_edge(comps: List[Any], arch: Any, ctx: ScoringContext) -> DimensionScore:
    """Media origin + edge delivery (streaming, video, education, social)."""
    cdn = 0.0
    if has_type(comps, "cdn"):
        cdn += 25.0
    if has_name_like(comps, "cdn", "edge", "cloudfront"):
        cdn += 10.0
    cdn = min(35.0, cdn)

    origin = 0.0
    if has_type(comps, "datastore"):
        origin += 20.0
    if has_name_like(comps, "media", "video", "storage", "s3"):
        origin += 10.0
    origin = min(30.0, origin)

    cache = min(20.0, count_type(comps, "cache") * 12.0) if has_type(comps, "cache") else 0.0

    fabric = 0.0
    if has_type(comps, "messaging"):
        fabric += 8.0
    if _comm(arch) in ("async", "event-driven"):
        fabric += 7.0
    fabric = min(15.0, fabric)

    score = cdn + origin + cache + fabric
    strengths, weaknesses = [], []
    if cdn >= 25:
        strengths.append("Edge CDN offloads playback from origin.")
    else:
        weaknesses.append("No edge delivery: origin will saturate on playback load.")
    if origin >= 20:
        strengths.append("Dedicated media origin store.")
    else:
        weaknesses.append("Media assets share the transactional database (bad).")
    if not strengths:
        strengths.append("Baseline media posture.")
    return DimensionScore(score, breakdown={"edge_delivery": round(cdn, 2), "origin_store": round(origin, 2), "cache": round(cache, 2), "fabric": round(fabric, 2)},
                          max_breakdown={"edge_delivery": 35.0, "origin_store": 30.0, "cache": 20.0, "fabric": 15.0},
                          strengths=strengths, weaknesses=weaknesses,
                          reason=f"Media {score:.1f}/100: edge {cdn:.0f}/35, origin {origin:.0f}/30, cache {cache:.0f}/20, fabric {fabric:.0f}/15.")


def evaluate_ingestion_scale(comps: List[Any], arch: Any, ctx: ScoringContext) -> DimensionScore:
    """Device-telemetry ingestion at scale (IoT)."""
    hub = 0.0
    if has_type(comps, "realtime", "messaging"):
        hub += 20.0
    if has_name_like(comps, "ingest", "device", "telemetry", "hub"):
        hub += 15.0
    hub = min(35.0, hub)

    n_q = count_type(comps, "messaging")
    buffering = min(25.0, 15.0 + 5.0 * n_q) if n_q else 3.0

    store = 0.0
    if has_type(comps, "datastore"):
        store += 15.0
    if has_name_like(comps, "time-series", "timeseries", "history", "telemetry"):
        store += 10.0
    store = min(25.0, store)

    headroom = 15.0 * (1.0 - 2.718 ** (-max((_instances(comps) * 1500) / max(ctx.expected_users, 100), 0.0) / 1.2))

    score = hub + buffering + store + headroom
    strengths, weaknesses = [], []
    if hub >= 20:
        strengths.append("Dedicated device-ingestion hub.")
    else:
        weaknesses.append("No ingestion hub: device telemetry has no front door.")
    if store >= 15:
        strengths.append("Time-series store retains high-cardinality telemetry.")
    else:
        weaknesses.append("No time-series store for device data.")
    if not strengths:
        strengths.append("Baseline ingestion posture.")
    return DimensionScore(score, breakdown={"ingest_hub": round(hub, 2), "buffering": round(buffering, 2), "ts_store": round(store, 2), "headroom": round(headroom, 2)},
                          max_breakdown={"ingest_hub": 35.0, "buffering": 25.0, "ts_store": 25.0, "headroom": 15.0},
                          strengths=strengths, weaknesses=weaknesses,
                          reason=f"Ingestion {score:.1f}/100: hub {hub:.0f}/35, buffer {buffering:.0f}/25, store {store:.0f}/25, headroom {headroom:.0f}/15.")


def evaluate_device_security(comps: List[Any], arch: Any, ctx: ScoringContext) -> DimensionScore:
    """Fleet identity & edge trust (IoT)."""
    identity = 0.0
    if has_name_like(comps, "device registry", "registry", "identity", "auth"):
        identity += 25.0
    if has_type(comps, "gateway"):
        identity += 15.0
    identity = min(40.0, identity)

    vault = 0.0
    if has_name_like(comps, "vault", "kms", "secrets"):
        vault += 20.0
    vault += min(10.0, count_type(comps, "security") * 5.0)
    vault = min(30.0, vault)

    transport = 0.0
    if has_name_like(comps, "waf", "firewall"):
        transport += 15.0
    if has_type(comps, "messaging"):
        transport += 15.0  # mutually-authenticated, segmented device transport
    transport = min(30.0, transport)

    score = identity + vault + transport
    strengths, weaknesses = [], []
    if identity >= 25:
        strengths.append("Fleet identity (registry/auth) at the edge.")
    else:
        weaknesses.append("No device identity: spoofed devices can inject data.")
    if vault >= 20:
        strengths.append("Managed device-key lifecycle.")
    else:
        weaknesses.append("No key/vault management for fleet credentials.")
    if not strengths:
        strengths.append("Baseline device-trust posture.")
    return DimensionScore(score, breakdown={"fleet_identity": round(identity, 2), "key_lifecycle": round(vault, 2), "segmented_transport": round(transport, 2)},
                          max_breakdown={"fleet_identity": 40.0, "key_lifecycle": 30.0, "segmented_transport": 30.0},
                          strengths=strengths, weaknesses=weaknesses,
                          reason=f"DeviceTrust {score:.1f}/100: identity {identity:.0f}/40, keys {vault:.0f}/30, transport {transport:.0f}/30.")


def evaluate_data_privacy(comps: List[Any], arch: Any, ctx: ScoringContext) -> DimensionScore:
    """PHI/PII minimization & encryption (healthcare)."""
    enc = 0.0
    if has_name_like(comps, "vault", "kms", "hsm", "secrets"):
        enc += 25.0
    if any(str(getattr(c, "type", "")).lower() == "database" and bool(getattr(c, "managed", False)) for c in comps):
        enc += 15.0
    enc = min(40.0, enc)

    audit = 0.0
    if has_name_like(comps, "audit"):
        audit += 20.0
    if ctx.compliance and has_name_like(comps, "audit"):
        audit += 10.0
    audit = min(30.0, audit)

    stores = count_type(comps, "datastore", "database")
    minimization = 20.0 if stores <= 2 else max(4.0, 20.0 - (stores - 2) * 6.0)
    access = 10.0 if has_type(comps, "gateway") else 2.0
    control = min(30.0, minimization + access)

    score = enc + audit + control
    strengths, weaknesses = [], []
    if enc >= 25:
        strengths.append("Encryption-at-rest with managed key lifecycle.")
    else:
        weaknesses.append("PHI/PII without vault-managed encryption.")
    if audit >= 20:
        strengths.append("Access audit trail for PHI disclosures.")
    else:
        weaknesses.append("No audit trail for record access (HIPAA risk).")
    if not strengths:
        strengths.append("Baseline privacy posture.")
    return DimensionScore(score, breakdown={"encryption": round(enc, 2), "access_audit": round(audit, 2), "minimization": round(control, 2)},
                          max_breakdown={"encryption": 40.0, "access_audit": 30.0, "minimization": 30.0},
                          strengths=strengths, weaknesses=weaknesses,
                          reason=f"Privacy {score:.1f}/100: encryption {enc:.0f}/40, audit {audit:.0f}/30, minimization {control:.0f}/30.")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PARAM_DEFS: Dict[str, Dict[str, Any]] = {
    "compliance_governance": {"label": "Compliance & Audit", "evaluate": evaluate_compliance_governance},
    "transactional_consistency": {"label": "Transactional Consistency", "evaluate": evaluate_transactional_consistency},
    "realtime_delivery": {"label": "Realtime Delivery", "evaluate": evaluate_realtime_delivery},
    "elastic_burst": {"label": "Burst Elasticity", "evaluate": evaluate_elastic_burst},
    "media_edge": {"label": "Media Edge Delivery", "evaluate": evaluate_media_edge},
    "ingestion_scale": {"label": "Ingestion Scale", "evaluate": evaluate_ingestion_scale},
    "device_security": {"label": "Device Trust", "evaluate": evaluate_device_security},
    "data_privacy": {"label": "Data Privacy (PHI/PII)", "evaluate": evaluate_data_privacy},
}

DOMAIN_PARAMS: Dict[str, List[str]] = {
    "banking": ["compliance_governance", "transactional_consistency"],
    "finance": ["compliance_governance", "transactional_consistency"],
    "healthcare": ["compliance_governance", "data_privacy"],
    "chat": ["realtime_delivery", "elastic_burst"],
    "messaging": ["realtime_delivery", "elastic_burst"],
    "gaming": ["realtime_delivery", "elastic_burst"],
    "streaming": ["media_edge", "elastic_burst"],
    "video": ["media_edge", "elastic_burst"],
    "iot": ["ingestion_scale", "device_security"],
    "e-commerce": ["transactional_consistency", "elastic_burst"],
    "ecommerce": ["transactional_consistency", "elastic_burst"],
    "food delivery": ["realtime_delivery", "elastic_burst"],
    "social": ["elastic_burst", "media_edge"],
    "ride-sharing": ["realtime_delivery", "elastic_burst"],
    "ride sharing": ["realtime_delivery", "elastic_burst"],
    "education": ["media_edge", "elastic_burst"],
    "learning": ["media_edge", "elastic_burst"],
}


def resolve_domain_params(application_type: str) -> List[str]:
    """Return extra parameter names for an application domain (max 2)."""
    lowered = (application_type or "").strip().lower()
    for key, params in DOMAIN_PARAMS.items():
        if key in lowered:
            return list(params[:2])
    return []


def evaluate_domain_params(architecture: Any, ctx: ScoringContext) -> Dict[str, DimensionScore]:
    """Evaluate all domain params applicable to the context's application type."""
    comps = _comps(architecture)
    out: Dict[str, DimensionScore] = {}
    for name in resolve_domain_params(ctx.application_type):
        fn = PARAM_DEFS[name]["evaluate"]
        try:
            out[name] = fn(comps, architecture, ctx)
        except Exception:
            out[name] = DimensionScore(0.0, reason=f"{name}: evaluation failed safely.")
    return out


def blend_overall(core_weighted: float, extras: Dict[str, DimensionScore]) -> float:
    """Blend core fitness with domain params (extras take EXTRA_SHARE)."""
    if not extras:
        return float(core_weighted)
    mean_extra = sum(s.score for s in extras.values()) / len(extras)
    return (1.0 - EXTRA_SHARE) * float(core_weighted) + EXTRA_SHARE * mean_extra


def blended_weights(core_weights: Dict[str, float], extras: Dict[str, DimensionScore]) -> Dict[str, float]:
    """Display weights over core dims + extras (sums to 1.0)."""
    if not extras:
        return {k: round(float(v), 4) for k, v in core_weights.items()}
    w: Dict[str, float] = {k: round(float(v) * (1.0 - EXTRA_SHARE), 4) for k, v in core_weights.items()}
    share = round(EXTRA_SHARE / len(extras), 4)
    for name in extras:
        w[name] = share
    drift = round(1.0 - sum(w.values()), 4)
    if drift:
        top = max(w, key=lambda k: w[k])
        w[top] = round(w[top] + drift, 4)
    return w
