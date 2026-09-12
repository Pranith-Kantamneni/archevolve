# ARCHEVOLVE — Agentic AI Framework for Automated Software System Design

## Overview

ARCHEVOLVE is an AlphaEvolve-inspired framework for automated software system architecture design. It generates multiple candidate architectures, evaluates them against multiple objectives (cost, security, reliability, performance, scalability), and evolves them through an LLM-assisted mutation loop until an optimized architecture is found.

## Problem Statement

LLMs can generate software architectures from requirements, but a single generated architecture may not satisfy all constraints or provide an optimal solution. ARCHEVOLVE addresses this by:

- Generating multiple candidate architectures
- Evaluating them against multiple objectives
- Using evolutionary algorithms to improve them
- Retaining useful experience across generations
- Producing a final optimized architecture and design report

## Installation

```bash
# Clone the repository
git clone https://github.com/yourname/archevolve.git
cd archevolve

# Install dependencies
pip install -r requirements.txt

# Or install directly
pip install .
```

## Requirements

- Python 3.11+
- No external API key required for basic operation (deterministic mode)
- Optional: LLM API key for LLM-assisted mutation mode

## Quick Start

```bash
# Run the demo pipeline
python3 -m archevolve.scripts.demo

# Or run the evolution engine directly
from archevolve.evolution.evolution_engine import EvolutionEngine

raw = "Build an e-commerce platform that supports 10,000 concurrent users"
engine = EvolutionEngine(population_size=5, max_generations=3)
results = engine.run(raw)
```

## Architecture

The system consists of the following modules:

| Module | Description |
|--------|-------------|
| `requirements` | Parses natural-language requirements into structured models |
| `generation` | Generates initial candidate architecture populations |
| `evaluation` | Multi-objective evaluators (cost, security, reliability, performance, scalability) |
| `fitness` | Fitness calculation engine with configurable weights |
| `selection` | Fitness-based selection mechanism |
| `mutation` | LLM-assisted or deterministic mutation operator |
| `memory` | Experience memory for storing successful design patterns |
| `evolution` | Evolution engine orchestrating the full loop |

## How It Works

1. **Requirement Parsing**: Natural-language requirements are parsed into structured models
2. **Initial Population**: Multiple diverse candidate architectures are generated
3. **Evaluation**: Each architecture is scored across 5 objectives
4. **Selection**: Top-performing candidates are selected for mutation
5. **Mutation**: Architectures are improved based on weaknesses and experience
6. **Evolution**: Process repeats for specified generations
7. **Result**: Best architecture is selected and a design report is generated

## Environment Setup

```bash
# Basic deterministic mode (no API key required)
export ARCHEVOLVE_MODE=mock

# Optional: LLM mode (requires API key)
export ARCHEVOLVE_LLM_API_KEY=sk-...
export ARCHEVOLVE_LLM_MODE=real
```

## Demo

Run the complete demo pipeline:

```bash
python3 -m archevolve.scripts.demo
```

See the demo output for a complete walkthrough of the evolutionary process.

## Running Tests

```bash
pytest archevolve/tests/
```

## Reproducing Experiments

```bash
python3 -m archevolve.scripts.experiment
```

See experiment results in the `results/` directory.