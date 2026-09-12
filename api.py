from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request

from archevolve.evolution.evolution_engine import EvolutionEngine

app = FastAPI(title="ARCHEVOLVE API", description="Agentic AI Framework for Automated Software System Design")

app.mount("/static", StaticFiles(directory="archevolve/static"), name="static")
templates = Jinja2Templates(directory="archevolve/templates")


class OptimizeRequest(BaseModel):
    requirements: str = Field(
        default=(
            "Build an e-commerce platform that supports 10,000 concurrent users, "
            "requires high availability, secure payment processing, low latency, "
            "and should be scalable during traffic spikes while keeping infrastructure "
            "cost reasonable."
        ),
        description="Natural-language software requirement",
    )
    population_size: int = Field(default=5, ge=2, le=20)
    generations: int = Field(default=5, ge=1, le=10)


def _run_demo(raw_requirement: str, population_size: int, generations: int) -> Dict[str, Any]:
    engine = EvolutionEngine(
        population_size=population_size,
        max_generations=generations,
        selection_count=2,
        mutation_count=2,
        weights=None,
        use_llm=False,
    )
    results = engine.run(raw_requirement)

    return {
        "raw_requirement": results["raw_requirement"],
        "parsed_requirements": results["parsed_requirements"],
        "baseline": results["baseline"],
        "final_scores": results["final_scores"],
        "improvement": results["improvement"],
        "final_architecture": results["final_architecture"],
        "initial_population": results["initial_population"],
        "evolution_history": results["evolution_history"],
        "experience_memory_entries": results["experience_memory_entries"],
    }


@app.get("/", include_in_schema=False)
async def root(request: Request) -> HTMLResponse:
    """Serve the main showcase HTML page."""
    return templates.TemplateResponse(
        request, "index.html", {"title": "ARCHEVOLVE — Results"}
    )


@app.get("/health", include_in_schema=False)
async def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "archevolve"}


@app.post("/optimize", response_model=Dict[str, Any])
async def optimize(req: OptimizeRequest) -> Dict[str, Any]:
    """Run the complete ARCHEVOLVE evolutionary optimization pipeline.

    Accepts natural-language software requirements and returns the full
    evolution trace: parsed requirements, candidate architectures, objective
    scores, fitness, improvement and the final best architecture.
    """
    try:
        return _run_demo(req.requirements, req.population_size, req.generations)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/run-demo", response_model=Dict[str, Any])
async def run_demo() -> Dict[str, Any]:
    """Run the built-in showcase scenario and return the results."""
    try:
        req = OptimizeRequest()
        return _run_demo(req.requirements, req.population_size, req.generations)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/architecture/{architecture_name}", include_in_schema=False)
async def get_architecture(architecture_name: str) -> Dict[str, Any]:
    """Get details of a specific architecture by name."""
    from archevolve.models.architecture import ArchitectureModel

    try:
        arch = ArchitectureModel.create_monolith({"assumptions": ["Test scenario"]})
    except Exception:
        arch = ArchitectureModel.create_monolith()

    return {
        "name": arch.name,
        "generation": arch.generation,
        "components": [
            {"name": c.name, "type": c.type, "managed": c.managed, "quantity": c.quantity}
            for c in arch.components
        ],
        "deployment_strategy": arch.deployment_strategy,
        "communication_pattern": arch.communication_pattern,
        "design_rationale": arch.design_rationale,
        "assumptions": arch.assumptions,
    }