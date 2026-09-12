#!/usr/bin/env python3
"""ARCHEVOLVE Demo Script.

Runs the complete evolutionary pipeline for automated software system design.
"""

from __future__ import annotations

import sys
from archevolve.evolution.evolution_engine import EvolutionEngine


DISPLAY_WIDTH = 60

def print_section(title: str) -> None:
    """Print a section header."""
    print("\n" + "=" * DISPLAY_WIDTH)
    print(f"  {title}")
    print("=" * DISPLAY_WIDTH)


def print_line(label: str, value: str = "", indent: int = 2) -> None:
    """Print a labeled line."""
    if value:
        print(" " * indent + f"{label}: {value}")
    else:
        print(" " * indent + label)


def print_table_line(labels: list, values: list, width1: int = 25, width2: int = 25) -> None:
    """Print a table row with two columns."""
    l1 = labels[0] if len(labels) > 0 else ""
    l2 = labels[1] if len(labels) > 1 else ""
    v1 = values[0] if len(values) > 0 else ""
    v2 = values[1] if len(values) > 1 else ""
    print(f"  {l1:<{width1}}  {v1:>{width2}}  {l2:<{width2}}  {v2:>{width2}}")


def demo_basic() -> None:
    """Run basic demo of the ARCHEVOLVE pipeline."""
    print_section("ARCHEVOLVE DEMO")
    print_line(" ", "Agentic AI Framework for Automated Software System Design")

    # Requirement
    print_section("1. REQUIREMENTS")
    raw_requirement = (
        "Build an e-commerce platform that supports 10,000 concurrent users, "
        "requires high availability, secure payment processing, low latency, "
        "and should be scalable during traffic spikes while keeping infrastructure "
        "cost reasonable."
    )
    print_line("Raw requirement", raw_requirement)

    # 2. PARSED REQUIREMENTS
    print_section("2. PARSED REQUIREMENTS")
    from archevolve.requirements import parse_requirement
    parsed = parse_requirement(raw_requirement)
    print_line("Expected users", str(parsed.expected_users) if parsed.expected_users else "not specified")
    print_line("Security level", parsed.security_level or "not specified")
    print_line("Cost sensitive", str(parsed.cost_sensitive))
    print_line("Scalability type", parsed.scalability_type or "not specified")
    print_line("Availability requirement", f"{parsed.availability_percentage}%" if parsed.availability_percentage else "not specified")

    # 3. INITIAL POPULATION
    print_section("3. INITIAL POPULATION")
    from archevolve.generation.architecture_generator import ArchitectureGenerator
    generator = ArchitectureGenerator(population_size=5, seed=42)
    population = generator.generate_initial_population(raw_requirement)
    print_line("Population size", str(len(population)))
    for i, arch in enumerate(population):
        comp_names = ", ".join(c.name for c in arch.components)
        print_line(f"  Candidate {i + 1}", f"{arch.name} [{comp_names}]")

    # 4-6. EVALUATION, RANKING, SELECTION (via EvolutionEngine)
    print_section("4. EVOLUTIONARY PROCESS")
    engine = EvolutionEngine(
        population_size=5,
        max_generations=5,
        selection_count=2,
        mutation_count=2,
        weights=None,
        use_llm=False,
    )
    results = engine.run(raw_requirement)

    print_line("Initial candidates", "5 architectures generated")
    print_line("Selection count", str(engine.selection_count))
    print_line("Mutation count", str(engine.mutation_count))

    # 7. MUTATION / EVOLUTION
    print_section("7. MUTATION / EVOLUTION")
    print_line("Generations run", f"{results['evolution_history']['generations_run']} generations")
    init_fitness = results["baseline"]["overall"]
    final_fitness = results["final_scores"]["overall"]
    print_line("  Initial best fitness", f"{init_fitness:.1f}")
    print_line("  Final best fitness", f"{final_fitness:.1f}")
    # Show some improvement details
    improvement = results["improvement"]
    improved_obj = [obj for obj, obj_imp in improvement.items() if obj_imp.get("absolute", 0) != 0]
    if improved_obj:
        print_line("  Objectives improved", ", ".join(improved_obj))
        for obj in improved_obj:
            obj_imp = improvement[obj]
            direction = "improved" if obj_imp["absolute"] > 0 else "worsened"
            print_line(f"    {obj}", f"{obj_imp['initial']:.1f} -> {obj_imp['final']:.1f} ({direction} {obj_imp['absolute']:.1f})")
    else:
        print_line("  Objectives improved", "none (fitness change only via weight adjustment)")

    # 8. GENERATION 1 (overview)
    print_section("8. GENERATION OVERVIEW")
    eval_hist = results["evolution_history"]["evaluation_history"]
    gen_count = len(eval_hist)
    print_line("Total generations", str(gen_count))
    print_line("Fitness progression", " -> ".join(f"{f:.1f}" for f in eval_hist[:gen_count]))

    # 9. EXPERIENCE MEMORY
    print_section("9. EXPERIENCE MEMORY")
    mem_entries = results["experience_memory_entries"]
    print_line("Experience entries", str(mem_entries))
    print_line("Patterns stored", "Design patterns and evolutionary feedback")

    # 10. FINAL ARCHITECTURE
    print_section("10. FINAL ARCHITECTURE")
    final_arch = results["final_architecture"]
    print_line("Best architecture", final_arch["name"])
    print_line("Fitness score", f"{results['final_scores']['overall']:.1f}")
    comp_names = ", ".join(c["name"] for c in final_arch["components"])
    print_line("Components", comp_names)

    # 11. BASELINE VS ARCHEVOLVE
    print_section("11. BASELINE VS ARCHEVOLVE")
    baseline = results["baseline"]
    final_scores = results["final_scores"]
    # Print table header
    print("  " + "=" * 50)
    print("  " + f"{' ':<25}  {'Baseline':>12}  {'ARCHEVOLVE':>12}")
    print("  " + "-" * 50)
    # Print each objective
    objectives = ["Cost", "Security", "Reliability", "Performance", "Scalability"]
    for i, obj in enumerate(objectives):
        b = baseline[objectives[i].lower()]
        f = final_scores[objectives[i].lower()]
        print(f"  {obj:<25}  {b:>12.1f}  {f:>12.1f}")
    print("  " + "-" * 50)
    print(f"  {'Fitness':<25}  {baseline['overall']:>12.1f}  {final_scores['overall']:>12.1f}")
    print("  " + "=" * 50)

    # 12. RESULTS
    print_section("12. RESULTS")
    improvement_abs = final_scores["overall"] - baseline["overall"]
    improvement_pct = (improvement_abs / max(baseline["overall"], 1e-10)) * 100
    print_line("  Initial fitness", f"{baseline['overall']:.1f}")
    print_line("  Final fitness", f"{final_scores['overall']:.1f}")
    print_line("  Absolute improvement", f"{improvement_abs:.1f}")
    print_line("  Percentage improvement", f"{improvement_pct:.1f}%")
    total_candidates = 5 + (results["evolution_history"]["generations_run"] or 0) * 2
    print_line("  Generations run", f"{results['evolution_history']['generations_run']}")
    print_line("  Candidates evaluated", str(total_candidates))

    # 13. DESIGN REPORT
    print_section("13. DESIGN REPORT")
    print_line("  Problem", raw_requirement)
    print_line("  Input requirements", raw_requirement)
    print_line("  Parsed requirements", f"Users: {parsed.expected_users}, Security: {parsed.security_level}, Cost-sensitive: {parsed.cost_sensitive}")
    print_line("  Final architecture", final_arch["name"])
    print_line("  Final fitness", f"{results['final_scores']['overall']:.1f}")
    print_line("  Generations run", f"{results['evolution_history']['generations_run']}")
    print_line("  Improvement", f"{improvement_pct:.1f}% overall fitness improvement")
    print()
    print("=" * DISPLAY_WIDTH)
    print("  DEMO COMPLETE")
    print("=" * DISPLAY_WIDTH)


def main() -> None:
    """Main entry point for the demo."""
    try:
        demo_basic()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()