from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, Optional

from .evolution.evolution_engine import EvolutionEngine

RUNS_DIR = os.path.join(os.path.dirname(__file__), "runs")

DEFAULT_REQUIREMENTS = (
    "Build a system that supports 10,000 concurrent users, requires high "
    "availability, low latency, and should scale during traffic spikes while "
    "keeping infrastructure cost reasonable."
)


def _runs_dir() -> str:
    directory = os.environ.get("ARCHEVOLVE_RUNS_DIR", RUNS_DIR)
    os.makedirs(directory, exist_ok=True)
    return directory


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _jsonable(value: Any) -> Any:
    """Recursively convert non-JSON-safe values into JSON-safe values."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return round(value, 4)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def run_optimization(
    application_type: Optional[str],
    requirements: str,
    constraints: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the ARCHEVOLVE pipeline for a user request and persist the result.

    Args:
        application_type: Application/system type (e.g. 'E-commerce platform')
        requirements: Free-text system requirements
        constraints: Optional free-text constraints

    Returns:
        A full result dictionary including a `run_id`.
    """
    constraints_dict = {}
    if constraints and constraints.strip():
        from .requirements.constraints import parse_constraints
        constraints_dict = parse_constraints(constraints)

    experience_path = os.environ.get(
        "ARCHEVOLVE_EXPERIENCE_PATH", "experience_memory.json"
    )

    engine = EvolutionEngine(
        population_size=5,
        max_generations=5,
        selection_count=2,
        mutation_count=2,
        weights=None,
        use_llm=False,
        experience_path=experience_path,
        application_type=application_type or "",
        constraints=constraints_dict,
    )

    results = engine.run(requirements)

    run_id = new_run_id()
    run_record = {
        "run_id": run_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "application_type": application_type or "",
        "requirements": requirements,
        "constraints_text": constraints or "",
        "constraints": constraints_dict,
        "results": _jsonable(results),
    }

    path = os.path.join(_runs_dir(), f"{run_id}.json")
    with open(path, "w") as f:
        json.dump(run_record, f, indent=2)

    run_record["results"]["run_id"] = run_id
    return run_record["results"]


def load_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Load a persisted run by run_id."""
    path = os.path.join(_runs_dir(), f"{run_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        record = json.load(f)
    results = record.get("results", {})
    results["run_id"] = run_id
    return results