#!/usr/bin/env python3
# start backend/src/scripts/utility_grimp_analysis.py
"""
Utility Grimp Analysis: Import Graph Analysis Using Grimp

Analyzes Python import relationships using the grimp library to find:
- Circular dependencies between modules
- Module coupling metrics (fan-in/fan-out)
- Package structure overview

Usage:
    python -m src.scripts.utility_grimp_analysis              # Auto-writes to docs/reports/
    python -m src.scripts.utility_grimp_analysis --stdout     # Print to stdout
    python -m src.scripts.utility_grimp_analysis --path src/
    python -m src.scripts.utility_grimp_analysis --output custom.txt
"""

import argparse
import sys
from contextlib import suppress
from datetime import datetime
from pathlib import Path

try:
    import grimp

    HAS_GRIMP = True
except ImportError:
    HAS_GRIMP = False


def find_circular_dependencies(graph: "grimp.ImportGraph") -> list[list[str]]:
    """Find circular dependency chains in the import graph."""
    cycles: list[list[str]] = []

    # Get all modules in the graph
    modules = graph.modules

    # Track visited modules for cycle detection
    visited: set[str] = set()
    rec_stack: set[str] = set()
    path: list[str] = []

    def dfs(module: str) -> None:
        if module in rec_stack:
            # Found a cycle - extract it from the path
            cycle_start = path.index(module)
            cycle = path[cycle_start:] + [module]
            cycles.append(cycle)
            return
        if module in visited:
            return

        visited.add(module)
        rec_stack.add(module)
        path.append(module)

        # Get modules that this module imports
        with suppress(Exception):
            imported = graph.find_modules_directly_imported_by(module)
            for imp in imported:
                dfs(imp)

        path.pop()
        rec_stack.remove(module)

    for module in modules:
        if module not in visited:
            dfs(module)

    return cycles


def calculate_coupling_metrics(
    graph: "grimp.ImportGraph",
) -> dict[str, dict[str, int]]:
    """Calculate fan-in (imports this) and fan-out (imported by this) for each module."""
    metrics: dict[str, dict[str, int]] = {}

    for module in graph.modules:
        try:
            fan_out = len(graph.find_modules_directly_imported_by(module))
            fan_in = len(graph.find_modules_that_directly_import(module))
            metrics[module] = {"fan_in": fan_in, "fan_out": fan_out}
        except Exception:
            metrics[module] = {"fan_in": 0, "fan_out": 0}

    return metrics


def _format_header_section(package_path: str, module_count: int) -> list[str]:
    """Format the header section of the report."""
    return [
        "=" * 70,
        "GRIMP IMPORT ANALYSIS",
        "=" * 70,
        f"Package: {package_path}",
        f"Modules analyzed: {module_count}",
        "",
    ]


def _format_cycles_section(cycles: list[list[str]]) -> list[str]:
    """Format the circular dependencies section."""
    if not cycles:
        return ["No circular dependencies found.", ""]

    lines = [
        "=" * 70,
        f"CIRCULAR DEPENDENCIES FOUND: {len(cycles)}",
        "=" * 70,
    ]
    for cycle in cycles:
        lines.append(f"  {' -> '.join(cycle)}")
    lines.append("")
    return lines


def _format_coupling_section(
    metrics: dict[str, dict[str, int]],
) -> tuple[list[str], dict[str, dict[str, int]]]:
    """Format the highly coupled modules section."""
    high_coupling = {
        k: v for k, v in metrics.items() if v["fan_in"] + v["fan_out"] > 10
    }

    lines = [
        "=" * 70,
        "HIGHLY COUPLED MODULES (>10 total connections)",
        "=" * 70,
    ]

    if high_coupling:
        sorted_coupling = sorted(
            high_coupling.items(),
            key=lambda x: x[1]["fan_in"] + x[1]["fan_out"],
            reverse=True,
        )
        for module, stats in sorted_coupling:
            total = stats["fan_in"] + stats["fan_out"]
            lines.append(
                f"  {module}: fan_in={stats['fan_in']}, "
                f"fan_out={stats['fan_out']} (total={total})"
            )
    else:
        lines.append("  No highly coupled modules found.")

    lines.append("")
    return lines, high_coupling


def _format_leaves_section(
    metrics: dict[str, dict[str, int]],
) -> tuple[list[str], list[str]]:
    """Format the leaf modules section."""
    leaves = [m for m, v in metrics.items() if v["fan_out"] == 0]
    if not leaves:
        return [], leaves

    lines = [
        "=" * 70,
        f"LEAF MODULES (no internal imports): {len(leaves)}",
        "=" * 70,
    ]
    for leaf in sorted(leaves)[:20]:
        lines.append(f"  - {leaf}")
    if len(leaves) > 20:
        lines.append(f"  ... and {len(leaves) - 20} more")

    return lines, leaves


def _format_summary_section(
    module_count: int, cycle_count: int, high_coupling_count: int, leaf_count: int
) -> list[str]:
    """Format the summary section."""
    return [
        "",
        "=" * 70,
        "SUMMARY",
        "=" * 70,
        f"  Total modules: {module_count}",
        f"  Circular dependencies: {cycle_count}",
        f"  Highly coupled modules: {high_coupling_count}",
        f"  Leaf modules: {leaf_count}",
    ]


def analyze_package(package_path: str) -> tuple[str, int]:
    """Analyze the package and return formatted output and exit code.

    Returns:
        Tuple of (output_text, exit_code)
        exit_code: 0 = success, 1 = issues found
    """
    if not HAS_GRIMP:
        return "ERROR: grimp library not installed. Install with: pip install grimp", 1

    output_lines: list[str] = []
    exit_code = 0

    try:
        # Build the import graph (exclude TYPE_CHECKING imports to avoid false positives)
        graph = grimp.build_graph(package_path, exclude_type_checking_imports=True)
        modules = list(graph.modules)

        output_lines.extend(_format_header_section(package_path, len(modules)))

        # Analyze and format circular dependencies
        cycles = find_circular_dependencies(graph)
        output_lines.extend(_format_cycles_section(cycles))
        if cycles:
            exit_code = 1

        # Calculate and format coupling metrics
        metrics = calculate_coupling_metrics(graph)
        coupling_lines, high_coupling = _format_coupling_section(metrics)
        output_lines.extend(coupling_lines)

        # Format leaf modules
        leaves_lines, leaves = _format_leaves_section(metrics)
        output_lines.extend(leaves_lines)

        # Add summary
        output_lines.extend(
            _format_summary_section(
                len(modules), len(cycles), len(high_coupling), len(leaves)
            )
        )

    except Exception as e:
        output_lines.append(f"ERROR: Failed to analyze package: {e}")
        exit_code = 1

    return "\n".join(output_lines), exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze Python import graph using grimp"
    )
    parser.add_argument(
        "--path", default="src", help="Package path to analyze (default: src)"
    )
    parser.add_argument(
        "--output",
        default="auto",
        help="Output file (default: auto-generated in docs/reports/)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout instead of writing to file",
    )
    args = parser.parse_args()

    # Run analysis
    output_content, exit_code = analyze_package(args.path)

    # Always print the full output
    print(output_content)

    # Also write to file unless --stdout is specified
    if not args.stdout:
        # Determine output path
        if args.output == "auto":
            reports_dir = Path("docs/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            output_path = reports_dir / f"grimp-{timestamp}.txt"
        else:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(output_content, encoding="utf-8")
        print(f"\nReport written to: {output_path}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

# end backend/src/scripts/utility_grimp_analysis.py
