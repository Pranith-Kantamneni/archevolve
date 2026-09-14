from __future__ import annotations

from typing import Dict, Any, List


def derive_connections(
    components: List[Any],
    communication_pattern: str = "sync",
    services: List[str] = None,
) -> List[Dict[str, str]]:
    """Derive a connection graph from a set of components.

    The graph is produced entirely from the actual component data (no hardcoded
    architecture), using simple rules:

    - Clients connect to the edge (gateway, or the first reachable service).
    - A gateway routes to every service / compute component.
    - When communication is async/event-driven, services also publish to the
      messaging component.
    - Services read/write databases and datastores, and use caches.
    - Real-time hubs route to services as well.

    Returns a list of edges: {"source": <component name>, "target": <component name>}
    """
    comps = [c for c in components]
    services = services or []

    conns: List[Dict[str, str]] = []

    def names_of(type_name: str) -> List[str]:
        return [c.name for c in comps if c.type == type_name]

    def is_service(c: Any) -> bool:
        if c.type == "service":
            return True
        if not services:
            return c.type in ("application", "compute")
        if c.type in ("application", "compute"):
            # Treat compute as a service endpoint when service list is available
            return c.name.lower() in [s.lower() for s in services]
        return False

    gateways = names_of("gateway")
    services = names_of("service")
    applications = names_of("application")
    computes = names_of("compute")
    messagings = names_of("messaging")
    databases = names_of("database")
    datastores = names_of("datastore")
    caches = names_of("cache")
    realtime = names_of("realtime")
    security = names_of("security")
    others = names_of("load balancer") + names_of("lb")

    edge_nodes = gateways or services or applications or computes or others

    # Clients -> entry point
    if edge_nodes:
        conns.append({"source": "Clients", "target": edge_nodes[0], "kind": "request"})

    # Entry point -> service / compute nodes
    if edge_nodes:
        for node in edge_nodes:
            targets = services + applications + computes
            for t in targets:
                if t != node:
                    conns.append({"source": node, "target": t, "kind": "route"})

    # Service-to-service via messaging (async patterns)
    if communication_pattern in ("async", "event-driven") and messagings:
        for s in services + applications:
            for m in messagings:
                conns.append({"source": s, "target": m, "kind": "publish"})

    # Real-time hubs receive client streams and route to service/compute nodes
    for rh in realtime:
        conns.append({"source": "Clients", "target": rh, "kind": "stream"})
        for s in services + applications + computes:
            conns.append({"source": rh, "target": s, "kind": "stream"})

    # Services read/write databases & datastores
    data_targets = databases + datastores
    for s in services + applications:
        for d in data_targets:
            conns.append({"source": s, "target": d, "kind": "read/write"})

    # Services use caches
    for s in services + applications:
        for c in caches:
            conns.append({"source": s, "target": c, "kind": "cache"})

    # Security components guard the entry + services
    for sec in security:
        if edge_nodes:
            conns.append({"source": "Clients", "target": sec, "kind": "filter"})
            conns.append({"source": sec, "target": edge_nodes[0], "kind": "protect"})
        for s in services:
            conns.append({"source": sec, "target": s, "kind": "protect"})

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for edge in conns:
        key = (edge["source"], edge["target"])
        if key not in seen:
            seen.add(key)
            unique.append(edge)
    return unique


def component_metadata(components: List[Any]) -> List[Dict[str, Any]]:
    """Serialize components into simple dicts for visualization."""
    return [
        {
            "name": c.name,
            "type": c.type,
            "quantity": c.quantity,
            "managed": c.managed,
        }
        for c in components
    ]