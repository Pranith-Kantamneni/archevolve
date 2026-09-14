from __future__ import annotations

import re
from typing import Dict, Any, List, Optional

PROVIDERS = ["aws", "amazon web services", "gcp", "google cloud", "azure", "microsoft azure"]
COMPLIANCE = ["gdpr", "hipaa", "pci-dss", "pci dss", "sox", "iso 27001"]
DATABASES = ["postgresql", "mysql", "mongodb", "cassandra", "dynamodb", "redis"]
TECH = [
    "kubernetes", "docker", "kafka", "rabbitmq", "graphql", "grpc", "react",
    "nodejs", "python", "java", "go", "lambda", "terraform", "snowflake", "s3",
]


def parse_constraints(text: Optional[str]) -> Dict[str, Any]:
    """Parse optional free-text constraints into a structured dict.

    Detects: max budget, cloud provider, preferred technologies, database
    preferences, compliance requirements and deployment environment.
    """
    if not text or not text.strip():
        return {}
    lowered = text.lower()
    constraints: Dict[str, Any] = {}

    # Maximum budget: "$5000/month" or "budget of 5000"
    match = re.search(r"\$?(\d[\d,]*(?:\.\d+)?)\s*(?:USD)?/?(?:month|mo)?", lowered)
    budget_match = re.search(r"(?:budget|cost|spend).{0,12}\$?\s*(\d[\d,]*(?:\.\d+)?)", lowered)
    if match:
        constraints["max_budget"] = float(match.group(1).replace(",", ""))
    elif budget_match:
        constraints["max_budget"] = float(budget_match.group(1).replace(",", ""))

    # Cloud provider
    for provider in PROVIDERS:
        if provider in lowered:
            constraints["provider"] = {
                "aws": "aws", "amazon web services": "aws",
                "gcp": "gcp", "google cloud": "gcp",
                "azure": "azure", "microsoft azure": "azure",
            }[provider]
            break

    # Compliance
    found_compliance = [c.upper().replace(" ", "-") for c in COMPLIANCE if c in lowered]
    if found_compliance:
        constraints["compliance"] = found_compliance

    # Database preference
    for db in DATABASES:
        if db in lowered:
            constraints["database"] = db
            break

    # Preferred technologies
    found_tech = [t for t in TECH if t in lowered]
    if found_tech:
        constraints["technologies"] = found_tech

    # Deployment environment
    if "on-prem" in lowered or "on premise" in lowered:
        constraints["deployment"] = "on-premise"
    elif "edge" in lowered:
        constraints["deployment"] = "edge"
    elif "cloud" in lowered:
        constraints["deployment"] = "cloud"

    return constraints


def apply_constraints_to_parsed(parsed: Any, constraints: Dict[str, Any]) -> Any:
    """Merge parsed constraint fields into a ParsedRequirement instance.

    Returns a new ParsedRequirement (immutable) if any field changed, otherwise
    the original instance.
    """
    updates: Dict[str, Any] = {}
    if constraints.get("max_budget"):
        updates["max_monthly_cost"] = float(constraints["max_budget"])
    if constraints.get("deployment"):
        updates["deployment_environment"] = constraints["deployment"]
    if constraints.get("compliance"):
        updates["compliance_requirements"] = constraints["compliance"]
    if constraints.get("technologies"):
        existing = set()
        for p in constraints["technologies"]:
            existing.add(p.strip())
        updates["preferred_technologies"] = sorted(
            existing | set(parsed.preferred_technologies)
        )
    if constraints.get("database") and "managed" not in updates:
        updates["preferred_technologies"] = sorted(
            set(parsed.preferred_technologies) | {constraints["database"]}
        )
    if not updates:
        return parsed

    data = parsed.model_dump()
    data.update(updates)
    from .models import ParsedRequirement
    return ParsedRequirement(**data)