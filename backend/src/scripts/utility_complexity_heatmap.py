#!/usr/bin/env python3
# start backend/src/scripts/utility_complexity_heatmap.py
"""
Utility Complexity Heatmap: Identify Refactoring Hotspots

Generates a heatmap of code complexity across the codebase:
- Cyclomatic complexity per function
- Maintainability index per file
- Identifies functions needing refactoring (CC > 10)

Usage:
    python -m src.scripts.utility_complexity_heatmap                  # All results to docs/reports/
    python -m src.scripts.utility_complexity_heatmap --stdout         # Print to stdout
    python -m src.scripts.utility_complexity_heatmap --limit 20       # Limit to top 20 per section
    python -m src.scripts.utility_complexity_heatmap --threshold 15 --format json
    python -m src.scripts.utility_complexity_heatmap --output custom.txt
"""

import argparse
import json
import logging
import operator
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from radon.complexity import cc_rank, cc_visit
    from radon.metrics import mi_visit

    HAS_RADON = True
except ImportError:
    HAS_RADON = False


@dataclass
class FunctionComplexity:
    file: str
    name: str
    line: int
    complexity: int
    rank: str


@dataclass
class FileMetrics:
    file: str
    maintainability_index: float
    functions: list[FunctionComplexity]


def analyze_file(file_path: Path) -> FileMetrics | None:
    """Analyze a single file for complexity metrics."""
    if not HAS_RADON:
        return None

    try:
        source = file_path.read_text(encoding="utf-8")
        blocks = cc_visit(source)
        mi = mi_visit(source, True)
    except Exception as e:
        logger.debug(f"Failed to analyze {file_path}: {e}")
        return None

    functions = [
        FunctionComplexity(
            file=str(file_path),
            name=block.name,
            line=block.lineno,
            complexity=block.complexity,
            rank=cc_rank(block.complexity),
        )
        for block in blocks
    ]

    return FileMetrics(
        file=str(file_path), maintainability_index=mi, functions=functions
    )


def scan_codebase(path: Path, threshold: int = 10) -> dict[str, Any]:
    """Scan entire codebase for complexity hotspots."""
    results: dict[str, Any] = {
        "summary": {
            "total_files": 0,
            "high_complexity_count": 0,
            "avg_mi": 0,
            "threshold": threshold,
        },
        "hotspots": [],
        "files": [],
    }

    mi_values: list[float] = []

    for root, dirs, files in os.walk(path):
        dirs[:] = [
            d
            for d in dirs
            if d not in {"venv", ".venv", "__pycache__", ".git", "tests"}
        ]
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                metrics = analyze_file(file_path)
                if metrics:
                    results["summary"]["total_files"] += 1
                    mi_values.append(metrics.maintainability_index)

                    # Add high-complexity functions to hotspots
                    for func in metrics.functions:
                        if func.complexity >= threshold:
                            results["summary"]["high_complexity_count"] += 1
                            results["hotspots"].append(
                                {
                                    "file": func.file,
                                    "function": func.name,
                                    "line": func.line,
                                    "complexity": func.complexity,
                                    "rank": func.rank,
                                }
                            )

                    results["files"].append(
                        {
                            "path": metrics.file,
                            "mi": round(metrics.maintainability_index, 2),
                            "function_count": len(metrics.functions),
                        }
                    )

    if mi_values:
        results["summary"]["avg_mi"] = round(sum(mi_values) / len(mi_values), 2)

    # Sort hotspots by complexity descending
    results["hotspots"].sort(key=operator.itemgetter("complexity"), reverse=True)

    return results


def _parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate complexity heatmap")
    parser.add_argument("--path", default="src", help="Path to analyze")
    parser.add_argument(
        "--threshold",
        type=int,
        default=10,
        help="CC threshold for hotspots (default: 10)",
    )
    parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
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
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit results per section (0 = no limit, show all)",
    )
    return parser.parse_args()


def _format_summary_section(summary: dict[str, Any]) -> list[str]:
    """Format the summary section of the report."""
    return [
        "=" * 70,
        "COMPLEXITY HEATMAP",
        "=" * 70,
        "\nSummary:",
        f"  Files analyzed: {summary['total_files']}",
        f"  Average maintainability index: {summary['avg_mi']}",
        f"  High-complexity functions (CC >= {summary['threshold']}): "
        f"{summary['high_complexity_count']}",
    ]


def _format_hotspots_section(hotspots: list[dict[str, Any]], limit: int) -> list[str]:
    """Format the hotspots section of the report."""
    if not hotspots:
        return ["\nNo high-complexity functions found."]

    lines = [
        f"\n{'=' * 70}",
        "HOTSPOTS (Functions needing refactoring)",
        "=" * 70,
    ]

    hotspots_to_show = hotspots[:limit] if limit > 0 else hotspots
    for h in hotspots_to_show:
        lines.append(
            f"  [{h['rank']}] CC={h['complexity']:2d}  "
            f"{h['file']}:{h['line']} {h['function']}"
        )

    if limit > 0 and len(hotspots) > limit:
        remaining = len(hotspots) - limit
        lines.append(f"  ... and {remaining} more hotspots")

    return lines


def _format_low_mi_section(files: list[dict[str, Any]], limit: int) -> list[str]:
    """Format the low maintainability files section."""
    low_mi = [f for f in files if f["mi"] < 50]
    if not low_mi:
        return []

    lines = [
        f"\n{'=' * 70}",
        "LOW MAINTAINABILITY FILES (MI < 50)",
        "=" * 70,
    ]

    sorted_low_mi = sorted(low_mi, key=operator.itemgetter("mi"))
    files_to_show = sorted_low_mi[:limit] if limit > 0 else sorted_low_mi

    for f in files_to_show:
        lines.append(f"  MI={f['mi']:5.1f}  {f['path']}")

    if limit > 0 and len(low_mi) > limit:
        lines.append(f"  ... and {len(low_mi) - limit} more files")

    return lines


def _format_distribution_section(files: list[dict[str, Any]]) -> list[str]:
    """Format the maintainability distribution section."""
    high_mi_count = len([f for f in files if f["mi"] >= 80])
    good_mi_count = len([f for f in files if 50 <= f["mi"] < 80])
    low_mi_count = len([f for f in files if f["mi"] < 50])

    return [
        f"\n{'=' * 70}",
        "MAINTAINABILITY DISTRIBUTION",
        "=" * 70,
        f"  Files with MI >= 80 (Excellent): {high_mi_count}",
        f"  Files with MI 50-79 (Good): {good_mi_count}",
        f"  Files with MI < 50 (Needs work): {low_mi_count}",
    ]


def _format_text_output(results: dict[str, Any], limit: int) -> str:
    """Format results as human-readable text."""
    lines: list[str] = []
    lines.extend(_format_summary_section(results["summary"]))
    lines.extend(_format_hotspots_section(results["hotspots"], limit))
    lines.extend(_format_low_mi_section(results["files"], limit))
    lines.extend(_format_distribution_section(results["files"]))
    return "\n".join(lines)


def _format_output(results: dict[str, Any], output_format: str, limit: int) -> str:
    """Format results based on output format."""
    if output_format == "json":
        return json.dumps(results, indent=2)
    return _format_text_output(results, limit)


def _determine_output_path(args: argparse.Namespace) -> Path:
    """Determine the output file path based on arguments."""
    if args.output != "auto":
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path

    reports_dir = Path("docs/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    ext = "json" if args.format == "json" else "txt"
    return reports_dir / f"complexity-heatmap-{timestamp}.{ext}"


def _write_output(content: str, args: argparse.Namespace) -> None:
    """Write output to file or stdout."""
    if args.stdout:
        print(content)
        return

    output_path = _determine_output_path(args)
    output_path.write_text(content, encoding="utf-8")
    print(f"Report written to: {output_path}")


def main() -> None:
    """Main entry point for complexity heatmap generation."""
    args = _parse_arguments()

    if not HAS_RADON:
        print("ERROR: radon not installed. Run: pip install radon")
        return

    results = scan_codebase(Path(args.path), args.threshold)
    output_content = _format_output(results, args.format, args.limit)
    _write_output(output_content, args)


if __name__ == "__main__":
    main()

# end backend/src/scripts/utility_complexity_heatmap.py
