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
- 📊 **Independent Multi-Objective Evaluators**: 5 dedicated evaluation agents providing scores, strengths, weaknesses, and clear reasoning for Cost, Security, Reliability, Performance, and Scalability.
- 🧠 **Dual Experience Memory (Successes & Failures)**: Retains high-scoring patterns and explicitly stores failed designs/anti-patterns to prevent repeating suboptimal decisions in future generations.
- 🔄 **Iterative Evolutionary Loop**: Weakness-driven mutations that directly address flaws diagnosed by the evaluation agents.
- 📈 **Baseline Comparison & Traceability**: Quantifies metric-by-metric improvements against standard monolithic/naive baselines and provides end-to-end agent decision logs.
- 🌐 **Interactive Web UI & FastAPI Backend**: Interactive dashboard featuring visual graph diagrams, generation-by-generation evolution traces, and memory exploration with success/failure filters.
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
| **Selection Agent** | Calculates weighted fitness across all 5 objectives and applies elitist selection. | Ranked population, survival decisions, selection log |
| **Architecture Evolution Agent** | Performs targeted mutations to resolve specific evaluator weaknesses using past experience. | Mutated candidate graphs with logged mutation actions |
| **Experience Memory Agent** | Stores winning design patterns and logs failed architectures / anti-patterns. | Retrieved successful patterns & failure warnings |
| **Final Architecture Agent** | Synthesizes the optimal architecture, tradeoff analysis, and comprehensive report. | Final design report, baseline diff, JSON export |

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
PYTHONPATH=.. python3 -m archevolve.scripts.demo
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

# 2. LLM-Assisted Mode (Optional)
export ARCHEVOLVE_MODE=real
export ARCHEVOLVE_LLM_API_KEY=your-api-key-here
export ARCHEVOLVE_LLM_MODEL=gpt-4o  # or claude-3-5-sonnet, gemini-1.5-pro
```

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