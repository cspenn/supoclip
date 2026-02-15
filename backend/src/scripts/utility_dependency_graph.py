#!/usr/bin/env python3
# start backend/src/scripts/utility_dependency_graph.py
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
import logging
import os
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_imports(file_path: Path) -> Iterator[str]:
    """Extract all imports from a Python file."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError, OSError) as e:
        logger.debug(f"Failed to parse {file_path}: {e}")
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


def _parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
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
    return parser.parse_args()


def _format_dot_output(graph: dict[str, set[str]]) -> list[str]:
    """Format output as Graphviz DOT format."""
    lines = [
        "digraph dependencies {",
        "    rankdir=LR;",
        "    node [shape=box];",
    ]
    for module, deps in graph.items():
        for dep in deps:
            lines.append(f'    "{module}" -> "{dep}";')
    lines.append("}")
    return lines


def _format_header_section(path: str, module_count: int) -> list[str]:
    """Format the header section of text output."""
    return [
        "=" * 70,
        "DEPENDENCY ANALYSIS",
        "=" * 70,
        f"Path: {path}",
        f"Modules analyzed: {module_count}",
    ]


def _format_cycles_section(cycles: list[list[str]]) -> list[str]:
    """Format the circular dependencies section."""
    if not cycles:
        return ["\nNo circular dependencies found."]

    lines = [
        f"\n{'=' * 70}",
        f"CIRCULAR DEPENDENCIES FOUND: {len(cycles)}",
        "=" * 70,
    ]
    for cycle in cycles:
        lines.append(f"  - {' -> '.join(cycle)}")
    return lines


def _format_coupling_section(coupling: dict[str, dict[str, int]]) -> list[str]:
    """Format the highly coupled modules section."""
    lines = [
        f"\n{'=' * 70}",
        "HIGHLY COUPLED MODULES (>5 connections)",
        "=" * 70,
    ]

    high_coupling = {
        k: v for k, v in coupling.items() if v["inbound"] + v["outbound"] > 5
    }

    if not high_coupling:
        lines.append("  No highly coupled modules found.")
        return lines

    for module, stats in sorted(
        high_coupling.items(),
        key=lambda x: x[1]["inbound"] + x[1]["outbound"],
        reverse=True,
    ):
        total = stats["inbound"] + stats["outbound"]
        lines.append(
            f"  {module}: "
            f"in={stats['inbound']}, out={stats['outbound']} "
            f"(total={total})"
        )

    return lines


def _format_leaves_section(graph: dict[str, set[str]]) -> list[str]:
    """Format the leaf modules section."""
    leaves = [m for m in graph if not graph[m]]
    if not leaves:
        return []

    lines = [
        f"\n{'=' * 70}",
        f"LEAF MODULES (no outbound dependencies): {len(leaves)}",
        "=" * 70,
    ]

    for leaf in sorted(leaves)[:20]:
        lines.append(f"  - {leaf}")

    if len(leaves) > 20:
        lines.append(f"  ... and {len(leaves) - 20} more")

    return lines


def _format_text_output(
    graph: dict[str, set[str]],
    cycles: list[list[str]],
    coupling: dict[str, dict[str, int]],
    path: str,
) -> list[str]:
    """Format output as human-readable text."""
    lines: list[str] = []
    lines.extend(_format_header_section(path, len(graph)))
    lines.extend(_format_cycles_section(cycles))
    lines.extend(_format_coupling_section(coupling))
    lines.extend(_format_leaves_section(graph))
    return lines


def _format_output(
    graph: dict[str, set[str]],
    cycles: list[list[str]],
    coupling: dict[str, dict[str, int]],
    args: argparse.Namespace,
) -> str:
    """Format output based on specified format."""
    if args.format == "dot":
        lines = _format_dot_output(graph)
    else:
        lines = _format_text_output(graph, cycles, coupling, args.path)
    return "\n".join(lines)


def _determine_output_path(args: argparse.Namespace) -> Path:
    """Determine the output file path based on arguments."""
    if args.output != "auto":
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path

    reports_dir = Path("docs/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    ext = "dot" if args.format == "dot" else "txt"
    return reports_dir / f"dependency-graph-{timestamp}.{ext}"


def _write_output(content: str, args: argparse.Namespace) -> None:
    """Write output to file or stdout."""
    if args.stdout:
        print(content)
        return

    output_path = _determine_output_path(args)
    output_path.write_text(content, encoding="utf-8")
    print(f"Report written to: {output_path}")


def main() -> None:
    """Main entry point for dependency graph analysis."""
    args = _parse_arguments()

    graph = build_dependency_graph(Path(args.path))
    cycles = find_cycles(graph)
    coupling = calculate_coupling(graph)

    output_content = _format_output(graph, cycles, coupling, args)
    _write_output(output_content, args)


if __name__ == "__main__":
    main()

# end backend/src/scripts/utility_dependency_graph.py
