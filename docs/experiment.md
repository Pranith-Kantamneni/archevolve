# ARCHEVOLVE Experiment Documentation

## Experiment Structure

For at least 3-5 test requirements/scenarios, run:

### A. Baseline
A single architecture generated without evolutionary optimization.

### B. ARCHEVOLVE
The architecture generated through the full evolutionary process.

### Comparison

Compare baseline vs ARCHEVOLVE on:

- **Cost**: baseline vs final
- **Security**: baseline vs final
- **Reliability**: baseline vs final
- **Performance**: baseline vs final
- **Scalability**: baseline vs final
- **Overall fitness**: baseline vs final
- **Number of generations**: evolution depth
- **Candidates evaluated**: total architectures scored
- **Improvement from initial to final**: absolute and percentage

### Machine-Readable Results

Results are saved under `results/`:

- `experiment_results.json`: JSON format with all scenario data
- `experiment_results.csv`: CSV format for spreadsheet analysis

### Generated Graphs

1. **Fitness vs Generation**: Progress of fitness across generations
2. **Objective Scores Before vs After Evolution**: Baseline vs ARCHEVOLVE scores
3. **Baseline vs ARCHEVOLVE Fitness**: Direct comparison chart
4. **Candidate Fitness Distribution by Generation**: Spread of scores

All graphs are generated using matplotlib from actual experiment data (not fabricated).

## Running Experiments

```bash
# Run experiments for multiple scenarios
python3 -m archevolve.scripts.experiment
```

### Experiment Configuration

Configure via `ExperimentConfig`:
- `population_size`: Number of candidates per generation
- `max_generations`: Maximum evolution depth
- `selection_count`: Top candidates to retain
- `mutation_count`: Mutations per selected candidate
- `weights`: Fitness function weights
- `use_llm`: Whether to use LLM for mutation
- `stopping_threshold`: Stop if fitness reaches this value

### Example Output

```
Baseline fitness: 72.0
ARCHEVOLVE fitness: 85.0

Improvement: 13.0 (18.1%)

Objective-wise improvements:
  Cost: 72 -> 78 (+6, +8.3%)
  Security: 74 -> 88 (+14, +18.9%)
  Reliability: 76 -> 86 (+10, +13.2%)
  Performance: 70 -> 84 (+14, +20.0%)
  Scalability: 68 -> 89 (+21, +30.9%)
```

## Reproducibility

Experiments are reproducible by:
- Using fixed random seeds (seed=42 by default)
- Configuring identical weights and parameters
- Running the same requirements through the pipeline
- Exporting and sharing results via JSON/CSV