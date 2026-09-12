# ARCHEVOLVE Demo Documentation

## Demo Overview

The demo runs the complete ARCHEVOLVE pipeline with a single command:

```bash
python3 -m archevolve.scripts.demo
```

## Demo Sequence

The demo prints the following sections:

### 1. REQUIREMENTS
The raw natural-language requirement text.

### 2. PARSED REQUIREMENTS
Structured extraction of the requirement including:
- Expected users/load
- Security level
- Cost sensitivity
- Scalability type
- Availability requirements

### 3. INITIAL POPULATION
5 diverse candidate architectures generated from the requirement:
- Candidate 1: Modular Monolith
- Candidate 2: Event-Driven
- Candidate 3: Microservices
- Candidate 4: Serverless
- Candidate 5: Variant

### 4. INITIAL EVALUATION
Each candidate is evaluated across 5 objectives with scores and reasoning:
- Cost, Security, Reliability, Performance, Scalability
- Overall fitness score

### 5. FITNESS RANKING
Candidates ranked by fitness (highest to lowest). Top 2 selected for mutation.

### 6. SELECTED ARCHITECTURES
The 2 selected architectures with their details and fitness scores.

### 7. MUTATION / EVOLUTION
Mutated versions of the selected architectures. Each mutation applies targeted improvements:
- Adding cache for performance
- Removing services for cost reduction
- Adding messaging for reliability/scalability

### 8. GENERATION 1
The new generation of evaluated architectures. Fitness typically improves.

### 8. EXPERIENCE MEMORY
Experience entries from the evolutionary process, storing:
- Successful design patterns
- Weaknesses identified
- Improvements observed

### 9. FINAL ARCHITECTURE
The best architecture from the final generation with:
- Name and fitness score
- Components and design
- Generation number

### 10. BASELINE VS ARCHEVOLVE
Comparison table showing:
- Baseline scores (single architecture, no evolution)
- ARCHEVOLVE scores (after evolution)
- Fitness improvement (absolute and percentage)

### 11. RESULTS
Summary of results:
- Initial fitness
- Final fitness
- Absolute improvement
- Percentage improvement
- Generations run
- Candidates evaluated

### 12. DESIGN REPORT
Concise report containing:
- Problem statement
- Input requirements
- Parsed requirements
- Initial candidate architectures
- Evaluation methodology
- Generation-wise scores
- Selected architectures
- Mutations applied
- Experience memory entries
- Final architecture
- Baseline comparison
- Limitations
- Future work

## Running the Demo

```bash
python3 -m archevolve.scripts.demo
```

### Expected Output

The demo produces console output showing all 13 sections of the pipeline, ending with "DEMO COMPLETE".

### Demo Without API Key

The demo runs entirely deterministically without requiring an API key. The `use_llm=False` flag ensures all mutation and generation is deterministic.

### Customizing the Demo

```python
from archevolve.evolution.evolution_engine import EvolutionEngine

engine = EvolutionEngine(
    population_size=5,
    max_generations=3,
    selection_count=2,
    mutation_count=2,
    use_llm=False,
)

results = engine.run("Your requirement here")
```

## Mock Mode

By default, the entire system runs in deterministic mock mode without API credentials. Set `ARCHEVOLVE_MODE=mock` or ensure no LLM API key is configured for offline operation.