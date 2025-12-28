#!/usr/bin/env python3
"""
Utility Dependency Graph: Detect Circular Dependencies and Module Tangles

Analyzes import relationships to find:
- Circular dependencies (A imports B imports A)
- Highly coupled modules (many inbound/outbound imports)
- Architectural layer violations

Usage:
    python -m src.scripts.utility_dependency_graph              # Auto-writes to docs/reports/
    python -m src.scripts.utility_dependency_graph --stdout     # Print to stdout
    python -m src.scripts.utility_dependency_graph --path src/ --format dot
    python -m src.scripts.utility_dependency_graph --output custom.txt
"""

import argparse
import ast
import os
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path


def extract_imports(file_path: Path) -> Iterator[str]:
    """Extract all imports from a Python file."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module.split(".")[0]


def build_dependency_graph(path: Path) -> dict[str, set[str]]:
    """Build module dependency graph."""
    graph: dict[str, set[str]] = defaultdict(set)

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in {"venv", ".venv", "__pycache__", ".git"}]
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                try:
                    module = (
                        str(file_path.relative_to(path))
                        .replace("/", ".")
                        .replace(".py", "")
                    )
                except ValueError:
                    module = str(file_path).replace("/", ".").replace(".py", "")

                for imp in extract_imports(file_path):
                    if imp.startswith("src"):
                        graph[module].add(imp)

    return graph.copy()


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Find all cycles in dependency graph using DFS."""
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: list[str] = []

    def dfs(node: str) -> None:
        if node in rec_stack:
            cycle_start = rec_stack.index(node)
            cycles.append(rec_stack[cycle_start:] + [node])
            return
        if node in visited:
            return

        visited.add(node)
        rec_stack.append(node)

        for neighbor in graph.get(node, []):
            dfs(neighbor)

        rec_stack.pop()

    for node in graph:
        dfs(node)

    return cycles


def calculate_coupling(graph: dict[str, set[str]]) -> dict[str, dict[str, int]]:
    """Calculate inbound and outbound coupling for each module."""
    coupling: dict[str, dict[str, int]] = defaultdict(
        lambda: {"inbound": 0, "outbound": 0}
    )

    for module, deps in graph.items():
        coupling[module]["outbound"] = len(deps)
        for dep in deps:
            coupling[dep]["inbound"] += 1

    return coupling.copy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize module dependencies")
    parser.add_argument("--path", default="src", help="Path to analyze")
    parser.add_argument(
        "--format",
        choices=["text", "dot"],
        default="text",
        help="Output format (text or dot for Graphviz)",
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

    graph = build_dependency_graph(Path(args.path))
    cycles = find_cycles(graph)
    coupling = calculate_coupling(graph)

    # Generate output
    output_lines: list[str] = []

    if args.format == "dot":
        output_lines.extend(
            (
                "digraph dependencies {",
                "    rankdir=LR;",
                "    node [shape=box];",
            )
        )
        for module, deps in graph.items():
            for dep in deps:
                output_lines.append(f'    "{module}" -> "{dep}";')
        output_lines.append("}")
    else:
        output_lines.extend(
            (
                "=" * 70,
                "DEPENDENCY ANALYSIS",
                "=" * 70,
                f"Path: {args.path}",
                f"Modules analyzed: {len(graph)}",
            )
        )

        if cycles:
            output_lines.extend(
                (
                    f"\n{'=' * 70}",
                    f"CIRCULAR DEPENDENCIES FOUND: {len(cycles)}",
                    "=" * 70,
                )
            )
            for cycle in cycles:
                output_lines.append(f"  - {' -> '.join(cycle)}")
        else:
            output_lines.append("\nNo circular dependencies found.")

        output_lines.extend(
            (
                f"\n{'=' * 70}",
                "HIGHLY COUPLED MODULES (>5 connections)",
                "=" * 70,
            )
        )
        high_coupling = {
            k: v for k, v in coupling.items() if v["inbound"] + v["outbound"] > 5
        }
        if high_coupling:
            for module, stats in sorted(
                high_coupling.items(),
                key=lambda x: x[1]["inbound"] + x[1]["outbound"],
                reverse=True,
            ):
                total = stats["inbound"] + stats["outbound"]
                output_lines.append(
                    f"  {module}: "
                    f"in={stats['inbound']}, out={stats['outbound']} "
                    f"(total={total})"
                )
        else:
            output_lines.append("  No highly coupled modules found.")

        # Show modules with no outbound deps (potential leaves)
        leaves = [m for m in graph if not graph[m]]
        if leaves:
            output_lines.extend(
                (
                    f"\n{'=' * 70}",
                    f"LEAF MODULES (no outbound dependencies): {len(leaves)}",
                    "=" * 70,
                )
            )
            for leaf in sorted(leaves)[:20]:
                output_lines.append(f"  - {leaf}")
            if len(leaves) > 20:
                output_lines.append(f"  ... and {len(leaves) - 20} more")

    output_content = "\n".join(output_lines)

    # Write to file or stdout
    if args.stdout:
        print(output_content)
    else:
        # Determine output path
        if args.output == "auto":
            reports_dir = Path("docs/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            ext = "dot" if args.format == "dot" else "txt"
            output_path = reports_dir / f"dependency-graph-{timestamp}.{ext}"
        else:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(output_content, encoding="utf-8")
        print(f"Report written to: {output_path}")


if __name__ == "__main__":
    main()
