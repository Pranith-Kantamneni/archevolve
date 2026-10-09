# ARCHEVOLVE — Multi-Agent Evolutionary AI Framework for Software Architecture Design

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Architecture: Multi-Agent](https://img.shields.io/badge/Architecture-Multi--Agent-green.svg)](#multi-agent-system-architecture)
[![Tests: 49 Passed](https://img.shields.io/badge/tests-49%20passed-brightgreen.svg)](#running-tests)
[![Mode: Deterministic & LLM](https://img.shields.io/badge/mode-Deterministic%20%7C%20LLM-orange.svg)](#environment-configuration)

---

## Overview

**ARCHEVOLVE** is an agentic, evolutionary AI framework for automated software system architecture design. Rather than relying on a single monolithic prompt, ARCHEVOLVE employs a **specialized multi-agent system** that collaborates, evaluates, critiques, and evolves software architectures across multiple generations.

The system generates candidate architectures, scores them through independent multi-objective evaluation agents (**Cost, Security, Reliability, Performance, Scalability**), applies experience-guided mutations to fix identified weaknesses, and synthesizes an optimal architecture with full design rationale and baseline comparisons.

---

## Key Features

- 🤖 **7 Specialized Autonomous Agents**: Clear division of responsibilities across requirement analysis, generation, evaluation, selection, mutation, memory, and final synthesis.
- 📊 **Requirement-Aware Earned-Points Scoring**: 5 dedicated evaluation agents (Cost, Security, Reliability, Performance, Scalability) score bottom-up from 0 across graded sub-criteria — conditioned on your requirements (users, latency SLA, availability target, budget, compliance) and application domain. Same architecture scores differently for banking vs. chat. Every score ships with per-criterion breakdowns and A–F grades.
- ⚖️ **Application-Aware Weights (+ Custom Override)**: Overall fitness weights adapt per domain (banking → security-heavy, real-time → performance-heavy) with requirement nudges (cost-sensitive, strict SLA, …). Override them from the UI — fill in any four percentages, mark the fifth Auto and it auto-fills so the total is exactly 100% — or via `"weights"` in `POST /optimize`.
- 🧩 **Domain-Specific Parameters**: Beyond the 5 universal dimensions, each domain is judged on what actually matters to it — banking/finance get *Compliance & Audit* + *Transactional Consistency*, chat/gaming get *Realtime Delivery* + *Burst Elasticity*, IoT gets *Ingestion Scale* + *Device Trust*, streaming gets *Media Edge Delivery*, healthcare gets *Data Privacy*. Blended at 20% into overall fitness with full breakdowns. New parameters plug in via `evaluation/domain_params.py`.
- 🧠 **Dual Experience Memory (Successes & Failures)**: Retains high-scoring patterns and explicitly stores failed designs/anti-patterns to prevent repeating suboptimal decisions in future generations.
- 🔄 **Iterative Evolutionary Loop**: Weakness-driven mutations that directly address flaws diagnosed by the evaluation agents.
- 📈 **Baseline Comparison & Traceability**: Quantifies metric-by-metric improvements against standard monolithic/naive baselines and provides end-to-end agent decision logs.
- 🌐 **Interactive Web UI & FastAPI Backend**: Interactive dashboard featuring visual graph diagrams (click **⛶ Expand** on any chart to open a fullscreen zoomable/downloadable view), generation-by-generation evolution traces, per-criterion score breakdowns, and memory exploration with success/failure filters.
- ⚡ **100% Functional Deterministic Mode**: Runs out-of-the-box without requiring external API keys, with optional plug-and-play LLM support.

---

## Multi-Agent System Architecture

```
                               ┌────────────────────────────────┐
                               │  Requirement Analysis Agent    │
                               │  (Parses constraints & goals)  │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │  Architecture Generation Agent │
                               │  (Diverse initial population)  │
                               └───────────────┬────────────────┘
                                               │
               ┌───────────────────────────────┴───────────────────────────────┐
               ▼                                                               ▼
 ┌───────────────────────────┐                                   ┌───────────────────────────┐
 │   Baseline Candidate      │                                   │   Population Candidates   │
 └─────────────┬─────────────┘                                   └─────────────┬─────────────┘
               │                                                               │
               └───────────────────────────────┬───────────────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │       Specialized Evaluation Agents       │
                         │ ├─ Cost Evaluator                         │
                         │ ├─ Security Evaluator                     │
                         │ ├─ Reliability Evaluator                  │
                         │ ├─ Performance Evaluator                  │
                         │ └─ Scalability Evaluator                  │
                         │ (Outputs: Score, Strengths, Flaws, Reason)│
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │        Selection Agent         │
                               │ (Ranks by fitness, elitism)    │
                               └───────────────┬────────────────┘
                                               │
        ┌──────────────────────────────────────┴──────────────────────────────────────┐
        ▼                                                                             ▼
┌───────────────────────────────┐                                     ┌───────────────────────────────┐
│     Experience Memory Agent   │ ◄─── (Queries positive patterns &   │   Evolution / Mutation Agent  │
│ (Stores Successes & Failures) │       anti-pattern warnings) ──────►│ (Weakness-driven mutations)   │
└───────────────────────────────┘                                     └───────────────┬───────────────┘
                                                                                      │
                                   (Repeat for N Generations) ◄───────────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │    Final Architecture Agent    │
                               │ (Synthesizes winning design,   │
                               │  rationale, report & trace)    │
                               └────────────────────────────────┘
```

---

## Agent Breakdown

| Agent | Responsibility | Key Outputs |
|---|---|---|
| **Requirement Analysis Agent** | Parses natural language into domain, requirements, scale, SLA, and constraints. | `StructuredRequirements` (tier, traffic, storage, latency targets) |
| **Architecture Generation Agent** | Generates diverse, structurally distinct initial architecture topologies. | Diverse population of candidate architecture graphs |
| **Cost Evaluator Agent** | Evaluates compute, database, caching, and operational infrastructure costs. | Score (0–1), strengths, weaknesses, cost breakdown |
| **Security Evaluator Agent** | Assesses zero-trust boundaries, auth layers, data encryption, and WAF defense. | Score (0–1), security gaps, strengths, rationale |
| **Reliability Evaluator Agent** | Evaluates multi-AZ redundancy, replication, health-checks, circuit breakers, backups. | Score (0–1), single-points-of-failure, resilience score |
| **Performance Evaluator Agent** | Evaluates response latency, caching efficiency, CDN presence, and async queues. | Score (0–1), bottleneck diagnostics, latency grade |
| **Scalability Evaluator Agent** | Checks horizontal auto-scaling, load balancing, DB sharding, and message queues. | Score (0–1), throughput headroom, scaling limits |
| **Selection Agent** | Calculates application-aware weighted fitness across all 5 objectives and applies elitist selection. | Ranked population, survival decisions, selection log |
| **Architecture Evolution Agent** | Performs targeted mutations to resolve specific evaluator weaknesses using past experience. | Mutated candidate graphs with logged mutation actions |
| **Experience Memory Agent** | Stores winning design patterns and logs failed architectures / anti-patterns. | Retrieved successful patterns & failure warnings |
| **Final Architecture Agent** | Synthesizes the optimal architecture, tradeoff analysis, and comprehensive report. | Final design report, baseline diff, JSON export |

---

## Scoring Methodology (Production-Grade Rubric)

Old approach (*"start at 100 and subtract penalties"* / *"start at 50 and add bonuses"*) saturated: nearly every candidate scored 90–100 on several dimensions, so evolution had no signal.

Current approach — **bottom-up, requirement-conditioned, continuous**:

1. **Earn from zero.** Each dimension starts at 0 and earns points across 4 graded sub-criteria (e.g. Cost = right-sizing /35 + budget-fit /30 + ops-efficiency /20 + elasticity-value /15). High scores are rare by construction.
2. **Heuristic ceiling: never 100/100.** Static analysis cannot verify runtime truth (live mTLS, key rotation, chaos drills, pentests), so every score is clamped to **97** (`HEURISTIC_CEILING` in `evaluation/scoring.py`, enforced centrally). The top band is reserved for production-verified systems — a 100 you see anywhere is a bug.
2. **Conditioned on your requirements.** Thresholds scale with parsed requirements: replica counts needed for full reliability marks grow with the availability target; edge-caching credit grows when the latency SLA is ≤100 ms; cost budget-fit uses your `$ budget` when given, else a per-user cost curve scaled by order of magnitude of users.
3. **Continuous curves, not cliffs.** Diminishing-return (`1 − e^(−(x/knee)^s)`) and logistic curves replace binary bonuses, so small architectural differences → small score differences.
4. **Application-aware weights.** `evaluation/scoring.py::resolve_weights` starts from a domain profile (banking weights security ≈ 30 %, chat weights performance ≈ 28 %, …), applies small requirement nudges, renormalizes, and honors explicit `"weights"` overrides from `POST /optimize` or the UI sliders.
5. **Transparent.** Every result carries `weights_used`, `weight_profile`, per-dimension `breakdowns` (earned/max per sub-criterion) and A–F `grades` — visible in the results page ("How this score is earned") and the API JSON.
6. **Extensible.** To add a parameter (e.g. maintainability): write `evaluation/<name>_evaluator.py` with an `evaluate(arch, context)` method returning score + breakdown + grade, register it in `DIMENSION_REGISTRY`, and add its weight to the domain profiles. For *domain-specific* parameters (only scored for matching applications), add an evaluator to `evaluation/domain_params.py` and attach it in `DOMAIN_PARAMS` — it is automatically blended at 20%, traced, and rendered in the UI.
7. **Verify-and-retry.** Every mutation is checked against its parent: non-improving children trigger one retry with a different pattern focused on the weakest dimension (duplicates are skipped, everything traced). Wins that crater a dimension without paying for it (drop > 10 pts, gain < 1.5× drop) trigger a guard retry (e.g. managed-premium guard). If evolution never beats the baseline, up to 2 recovery rounds run before finalization, and a `Verify Improvement` trace records per-parameter ▲/▼ at the end. The baseline is always the *best* initial candidate, so improvement claims measure evolution's work honestly.

### Example: same architectures, different applications

| Candidate | Banking (sec-heavy) | Chat (perf-heavy) |
|---|---|---|
| Modular Monolith | ~39 | ~43 |
| Microservices + cache/queue | ~56 | ~61 |

Scores differ because thresholds *and* weights move with the application — the signal evolution optimizes is meaningful per use-case.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/yourname/archevolve.git
cd archevolve

# Install dependencies
pip install -r requirements.txt

# Or install in editable mode
pip install -e .
```

---

## Quick Start

### 1. Launch Interactive Web Dashboard

Start the FastAPI application and open your browser:

```bash
PYTHONPATH=.. uvicorn archevolve.api:app --host 0.0.0.0 --port 8000 --reload
```

Open **[http://localhost:8000](http://localhost:8000)** to:
- Enter natural language requirements or select pre-built templates (E-Commerce, FinTech, IoT, Streaming).
- View the **Evolutionary Progress** across generations with fitness convergence charts.
- Compare the **Final Evolved Architecture vs Baseline** side-by-side.
- Inspect the **Agent Evolution Trace** showing decisions made at every step.
- Browse the **Experience Memory** bank with dedicated **Successes** and **Failures** filters.

---

### 2. Run CLI Pipeline Demo

Run the end-to-end multi-agent demonstration from the command line:

```bash
PYTHONPATH=.. python3 -m archevolve.scripts.demo [--users <number>]
```

---

### 3. Programmatic Python API

```python
from archevolve.agents.orchestrator import MultiAgentOrchestrator

orchestrator = MultiAgentOrchestrator(
    population_size=4,
    max_generations=3,
    mutation_rate=0.7,
)

raw_prompt = (
    "Build a high-traffic FinTech payment processing gateway handling "
    "50,000 TPS with strict 99.999% SLA, PCI-DSS compliance, and sub-50ms latency."
)

# Run full multi-agent evolution
results = orchestrator.run(raw_prompt)

print(f"Optimal Architecture: {results['best_candidate']['name']}")
print(f"Final Fitness Score: {results['best_candidate']['fitness']:.4f}")
print(f"Baseline Fitness:    {results['baseline_candidate']['fitness']:.4f}")
print(f"Improvement:         +{results['improvement_percent']:.1f}%")
print(f"Design Rationale:\n{results['design_rationale']}")
```

---

## Dual Experience Memory System

Unlike naive generative loops, ARCHEVOLVE maintains an explicit **dual-channel experience memory**:

1. **Success Memory**: Records high-performing structural patterns (e.g., *Multi-AZ Read Replicas + Redis Cluster + Asynchronous Message Queue*) to boost future mutations.
2. **Failure Memory**: Records low-scoring anti-patterns and evaluator rejections (e.g., *Uncached Relational DB under heavy write load*, *Single Point of Failure without replication*) so mutation agents actively avoid repeated mistakes.

You can inspect recorded experiences via the Web UI tab or via the API endpoint:
```bash
curl http://localhost:8000/api/experience
```

---

## Environment Configuration

ARCHEVOLVE operates seamlessly in both deterministic mock mode (offline, reproducible) and LLM-assisted mode:

```bash
# 1. Deterministic Mode (Default - No API key needed)
export ARCHEVOLVE_MODE=mock

# 2. LLM-Assisted Mode (Optional - real provider calls with safe fallback)
export ARCHEVOLVE_MODE=real
export ARCHEVOLVE_LLM_API_KEY=your-api-key-here
export ARCHEVOLVE_LLM_MODEL=gpt-4o  # or claude-3-5-sonnet, gemini-1.5-pro, ...
# Optional: point at any OpenAI-compatible gateway (Azure, LiteLLM, Ollama, ...)
export ARCHEVOLVE_LLM_BASE_URL=https://api.openai.com/v1
```

In LLM mode the deterministic rubric still computes every score; the LLM is
consulted for tradeoff synthesis (final rationale) and any provider failure
silently falls back to rule logic — runs are never blocked by the network.

---

## Running Tests

Run the comprehensive test suite (unit tests, agent tests, evaluators, memory, evolution loop, and API endpoints):

```bash
PYTHONPATH=.. pytest tests/ -v
```

---

## Project Structure

```
archevolve/
├── agents/                       # Specialized Multi-Agent System
│   ├── base.py                   # BaseAgent, AgentTraceEntry, LLMClient
│   ├── requirement_agent.py      # Requirement Analysis Agent
│   ├── generation_agent.py       # Architecture Generation Agent
│   ├── evaluation_agents.py      # 5x Specialized Evaluation Agents
│   ├── selection_agent.py        # Selection Agent
│   ├── mutation_agent.py         # Architecture Evolution / Mutation Agent
│   ├── memory_agent.py           # Experience Memory Agent
│   ├── final_architecture_agent.py # Final Synthesis & Reporting Agent
│   └── orchestrator.py           # MultiAgentOrchestrator
├── evaluation/                   # Evaluator scoring logic & diagnostics
│   ├── cost_evaluator.py         # Cost evaluation
│   ├── security_evaluator.py     # Security evaluation
│   ├── reliability_evaluator.py  # Reliability evaluation
│   ├── performance_evaluator.py  # Performance evaluation
│   └── scalability_evaluator.py  # Scalability evaluation
├── memory/                       # Experience persistence
│   └── experience_memory.py      # Dual success/failure storage & query
├── models/                       # Core domain models
│   ├── architecture.py           # Component & connection schema
│   └── graph.py                  # Topology graph helpers
├── static/                       # Web UI CSS & JavaScript
├── templates/                    # Web UI HTML templates
├── api.py                        # FastAPI endpoints & web application
├── scripts/
│   ├── demo.py                   # CLI multi-agent demo
│   └── experiment.py             # Benchmarking script
└── tests/                        # 49 unit and integration tests
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.