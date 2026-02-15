#!/usr/bin/env python3
# start backend/src/scripts/utility_xray.py
"""
Utility X-Ray: Architectural Skeletonizer with Complexity Metrics

Generates a compact representation of the codebase structure with:
- Class/function signatures (no implementations)
- Cyclomatic complexity scores (warns if CC > 10)
- Dependencies between modules

Feed the output to LLM for context when working on the codebase.

Usage:
    python -m src.scripts.utility_xray                    # Auto-writes to docs/reports/
    python -m src.scripts.utility_xray --stdout           # Print to stdout
    python -m src.scripts.utility_xray --path src/database/
    python -m src.scripts.utility_xray --format json
    python -m src.scripts.utility_xray --output custom.txt
"""

import argparse
import ast
import json
import logging
import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Import radon if available, otherwise provide fallback
try:
    from radon.complexity import cc_visit

    HAS_RADON = True
except ImportError:
    HAS_RADON = False


def get_complexity_map(source_code: str) -> dict[int, int]:
    """Get cyclomatic complexity per line number."""
    if not HAS_RADON:
        return {}
    try:
        blocks = cc_visit(source_code)
        return {block.lineno: block.complexity for block in blocks}
    except Exception as e:
        logger.debug(f"Failed to compute complexity: {e}")
        return {}


def generate_skeleton(file_path: Path) -> str:
    """Generate skeleton representation of a Python file."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        cmap = get_complexity_map(source)
    except Exception as e:
        return f"# Error parsing {file_path}: {e}"

    lines: list[str] = []

    class SkeletonVisitor(ast.NodeVisitor):
        indent = 0

        def log(self, text: str, complexity: int | None = None) -> None:
            warning = f"  # CC:{complexity}" if complexity and complexity > 10 else ""
            lines.append("    " * self.indent + text + warning)

        def visit_Import(self, node: ast.Import) -> None:
            names = ", ".join(alias.name for alias in node.names)
            self.log(f"import {names}")

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            names = ", ".join(alias.name for alias in node.names)
            module = node.module or ""
            self.log(f"from {module} import {names}")

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            bases = ", ".join(ast.unparse(b) for b in node.bases) if node.bases else ""
            base_str = f"({bases})" if bases else ""
            self.log(f"class {node.name}{base_str}:")
            self.indent += 1
            self.generic_visit(node)
            self.indent -= 1

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            args = ", ".join(a.arg for a in node.args.args)
            returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            complexity = cmap.get(node.lineno)
            self.log(f"def {node.name}({args}){returns}:", complexity)
            self.indent += 1
            self.log("...")
            self.indent -= 1

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            args = ", ".join(a.arg for a in node.args.args)
            returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            complexity = cmap.get(node.lineno)
            self.log(f"async def {node.name}({args}){returns}:", complexity)
            self.indent += 1
            self.log("...")
            self.indent -= 1

    SkeletonVisitor().visit(tree)
    return "\n".join(lines)


def scan_directory(
    path: Path, exclude_dirs: set[str] | None = None
) -> Iterator[tuple[Path, str]]:
    """Scan directory for Python files and generate skeletons."""
    exclude_dirs = exclude_dirs or {
        "venv",
        ".venv",
        "__pycache__",
        ".git",
        "node_modules",
    }

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                skeleton = generate_skeleton(file_path)
                yield file_path, skeleton


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate codebase X-ray with complexity metrics"
    )
    parser.add_argument("--path", default="src", help="Path to scan (default: src)")
    parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )
    parser.add_argument(
        "--exclude", nargs="*", default=[], help="Directories to exclude"
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

    exclude_dirs = {"venv", ".venv", "__pycache__", ".git", "node_modules", "tests"}
    exclude_dirs.update(args.exclude)

    results: dict[str, str] = {}
    for file_path, skeleton in scan_directory(Path(args.path), exclude_dirs):
        rel_path = str(file_path)
        results[rel_path] = skeleton

    # Generate output
    output_lines: list[str] = []
    if args.format == "json":
        output_lines.append(json.dumps(results, indent=2))
    else:
        output_lines.extend(
            (
                "=" * 70,
                "CODEBASE X-RAY (Architectural Skeleton)",
                "=" * 70,
                f"Path: {args.path}",
                f"Files: {len(results)}",
            )
        )
        if not HAS_RADON:
            output_lines.append(
                "Note: radon not installed - complexity scores unavailable"
            )
        output_lines.append("=" * 70)

        for path, skeleton in sorted(results.items()):
            output_lines.extend((f"\n# FILE: {path}", skeleton))

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
            ext = "json" if args.format == "json" else "txt"
            output_path = reports_dir / f"xray-{timestamp}.{ext}"
        else:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(output_content, encoding="utf-8")
        print(f"Report written to: {output_path}")


if __name__ == "__main__":
    main()

# end backend/src/scripts/utility_xray.py
