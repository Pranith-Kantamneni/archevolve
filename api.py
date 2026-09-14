from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request

from archevolve.runner import run_optimization, load_run, _runs_dir

app = FastAPI(
    title="ARCHEVOLVE",
    description="Agentic AI Framework for Automated Software System Design",
)

app.mount("/static", StaticFiles(directory="archevolve/static"), name="static")
templates = Jinja2Templates(directory="archevolve/templates")


class OptimizeRequest(BaseModel):
    application_type: str = Field(
        default="",
        description="Application / system type, e.g. 'E-commerce platform'",
    )
    requirements: str = Field(
        default="",
        description="Natural-language system requirements",
    )
    constraints: Optional[str] = Field(
        default="",
        description="Optional additional constraints (budget, provider, compliance, ...)",
    )


class RunSummary(BaseModel):
    run_id: str
    application_type: str
    created_at: str
    final_fitness: Optional[float] = None
    improvement_pct: Optional[float] = None


@app.get("/", include_in_schema=False)
async def root(request: Request) -> HTMLResponse:
    """Serve the input/home page."""
    return templates.TemplateResponse(request, "index.html", {"title": "ARCHEVOLVE"})


@app.get("/health", include_in_schema=False)
async def health() -> Dict[str, str]:
    return {"status": "healthy", "service": "archevolve"}


@app.post("/optimize", response_model=Dict[str, Any])
async def optimize(req: OptimizeRequest) -> Dict[str, Any]:
    """Run the full ARCHEVOLVE pipeline for the user's requirements.

    The backend/core engine is the single source of truth: all architectures,
    evaluations, scores and evolution history are computed here.
    """
    requirements = (req.requirements or "").strip()
    app_type = (req.application_type or "").strip()

    if not requirements:
        raise HTTPException(
            status_code=422, detail="System requirements must not be empty."
        )
    if len(requirements) < 10:
        raise HTTPException(
            status_code=422,
            detail="Please provide a more detailed description of the system requirements.",
        )

    try:
        return run_optimization(app_type, requirements, req.constraints)
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Optimization failed: {e}")


@app.get("/results/{run_id}", include_in_schema=False)
async def results_page(request: Request, run_id: str) -> HTMLResponse:
    """Serve the results page for a specific run."""
    return templates.TemplateResponse(
        request, "results.html", {"title": "ARCHEVOLVE — Results", "run_id": run_id}
    )


@app.get("/api/results/{run_id}", response_model=Dict[str, Any])
async def get_results(run_id: str) -> Dict[str, Any]:
    """Return the persisted result for a run."""
    result = load_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return result


@app.get("/api/runs", response_model=List[RunSummary])
async def list_runs(limit: int = 20) -> List[RunSummary]:
    """List recent runs, newest first."""
    import json

    summaries: List[RunSummary] = []
    directory = _runs_dir()
    files = []
    for name in os.listdir(directory):
        if name.endswith(".json"):
            path = os.path.join(directory, name)
            files.append((os.path.getmtime(path), path))
    files.sort(reverse=True)

    for _, path in files[: max(1, min(limit, 100))]:
        try:
            with open(path) as f:
                record = json.load(f)
            results = record.get("results", {})
            final = results.get("final_scores", {}).get("overall")
            base = results.get("baseline", {}).get("overall") or 0
            pct = ((final - base) / max(base, 1e-10) * 100) if final is not None else None
            summaries.append(
                RunSummary(
                    run_id=record.get("run_id", ""),
                    application_type=record.get("application_type", ""),
                    created_at=record.get("created_at", ""),
                    final_fitness=final,
                    improvement_pct=round(pct, 2) if pct is not None else None,
                )
            )
        except (json.JSONDecodeError, OSError):
            continue
    return summaries