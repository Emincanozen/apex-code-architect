"""AST Blast-Radius and Cyclomatic Complexity Analyzer for Apex Code Architect.

Scans Python, JavaScript, and TypeScript modules in a repository to compute:
- Per-function cyclomatic complexity and line counts
- Module import graphs and reverse-dependency blast radius (fan-in)
- Syntax/parse integrity and configurable complexity gates
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".pytest_cache",
}

PY_EXTENSIONS = {".py"}
JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?\s+from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\))"""
)
JS_FUNC_RE = re.compile(
    r"""(?:^|\s)(?:export\s+)?(?:async\s+)?(?:function\s+([A-Za-z_$][\w$]*)|const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)"""
)
JS_BRANCH_RE = re.compile(r"\b(?:if|else\s+if|for|while|case|catch)\b|\?\s*[^:]+\s*:|&&|\|\|")


@dataclass
class FunctionMetric:
    """Complexity and size metrics for a single function or method."""

    name: str
    lineno: int
    lines: int
    complexity: int


@dataclass
class FileAnalysis:
    """Structural metrics for one source file."""

    path: str
    language: str
    loc: int
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    functions: list[FunctionMetric] = field(default_factory=list)
    max_complexity: int = 0
    avg_complexity: float = 0.0
    reverse_dependents: list[str] = field(default_factory=list)
    blast_radius_score: int = 0
    parse_error: str | None = None


def _compute_py_complexity(node: ast.AST) -> int:
    """Calculate McCabe-style cyclomatic complexity for a Python AST node."""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.ExceptHandler,
                ast.With,
                ast.AsyncWith,
                ast.IfExp,
                ast.comprehension,
            ),
        ):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += max(0, len(child.values) - 1)
    return complexity


def _extract_py_imports(tree: ast.AST) -> list[str]:
    """Extract unique imported module identifiers from a Python AST."""
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return sorted(set(imports))


def _analyze_python_file(file_path: Path, rel_path: str, source: str) -> FileAnalysis:
    """Analyze a Python file using the standard library AST parser."""
    loc = len(source.splitlines())
    analysis = FileAnalysis(path=rel_path, language="python", loc=loc)
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as exc:
        analysis.parse_error = f"SyntaxError at line {exc.lineno}: {exc.msg}"
        return analysis

    analysis.imports = _extract_py_imports(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            analysis.classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_line = getattr(node, "end_lineno", node.lineno) or node.lineno
            fn_lines = max(1, end_line - node.lineno + 1)
            analysis.functions.append(
                FunctionMetric(
                    name=node.name,
                    lineno=node.lineno,
                    lines=fn_lines,
                    complexity=_compute_py_complexity(node),
                )
            )
    _finalize_complexity_stats(analysis)
    return analysis


def _analyze_js_file(rel_path: str, source: str) -> FileAnalysis:
    """Analyze JS/TS modules with lightweight structural scanning."""
    lines = source.splitlines()
    analysis = FileAnalysis(path=rel_path, language="js/ts", loc=len(lines))
    raw_imports = []
    for match in JS_IMPORT_RE.finditer(source):
        target = match.group(1) or match.group(2)
        if target:
            raw_imports.append(target)
    analysis.imports = sorted(set(raw_imports))

    for idx, line in enumerate(lines, start=1):
        match = JS_FUNC_RE.search(line)
        if match:
            fn_name = match.group(1) or match.group(2) or "<anonymous>"
            window_text = "\n".join(lines[idx - 1 : min(len(lines), idx + 45)])
            branch_hits = len(JS_BRANCH_RE.findall(window_text))
            analysis.functions.append(
                FunctionMetric(
                    name=fn_name,
                    lineno=idx,
                    lines=min(45, len(lines) - idx + 1),
                    complexity=1 + branch_hits,
                )
            )

    if not analysis.functions and lines:
        total_branches = len(JS_BRANCH_RE.findall(source))
        analysis.functions.append(
            FunctionMetric(name="<module>", lineno=1, lines=len(lines), complexity=1 + total_branches)
        )
    _finalize_complexity_stats(analysis)
    return analysis


def _finalize_complexity_stats(analysis: FileAnalysis) -> None:
    """Populate aggregate max and average complexity fields."""
    if not analysis.functions:
        return
    complexities = [fn.complexity for fn in analysis.functions]
    analysis.max_complexity = max(complexities)
    analysis.avg_complexity = round(sum(complexities) / len(complexities), 2)


def _iter_source_files(root: Path) -> Iterable[Path]:
    """Yield supported source files under root while pruning ignored directories."""
    if root.is_file():
        if root.suffix in PY_EXTENSIONS | JS_EXTENSIONS:
            yield root
        return

    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        for filename in sorted(files):
            candidate = Path(current) / filename
            if candidate.suffix in PY_EXTENSIONS | JS_EXTENSIONS:
                yield candidate


def _resolve_blast_radius(analyses: list[FileAnalysis]) -> None:
    """Compute reverse-dependency fan-in across scanned repository modules."""
    stem_to_paths: dict[str, list[str]] = {}
    for item in analyses:
        stem = Path(item.path).stem
        if stem != "__init__":
            stem_to_paths.setdefault(stem, []).append(item.path)

    dependents_map: dict[str, set[str]] = {item.path: set() for item in analyses}
    for item in analyses:
        for imp in item.imports:
            imp_tail = imp.replace("\\", "/").split("/")[-1].split(".")[-1]
            if not imp_tail:
                continue
            for target_path in stem_to_paths.get(imp_tail, []):
                if target_path != item.path:
                    dependents_map[target_path].add(item.path)

    for item in analyses:
        deps = sorted(dependents_map[item.path])
        item.reverse_dependents = deps
        item.blast_radius_score = len(deps) * 2 + item.max_complexity


def _scan_single_file(src_path: Path, base_dir: Path) -> FileAnalysis:
    """Read and dispatch a single file to its language-specific analyzer."""
    rel = src_path.relative_to(base_dir).as_posix()
    try:
        content = src_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return FileAnalysis(path=rel, language="unknown", loc=0, parse_error=str(exc))

    if src_path.suffix in PY_EXTENSIONS:
        return _analyze_python_file(src_path, rel, content)
    return _analyze_js_file(rel, content)


def _collect_violations(analyses: list[FileAnalysis], max_complexity: int) -> list[dict]:
    """Collect parse errors and functions exceeding the complexity gate."""
    violations: list[dict] = []
    for item in analyses:
        if item.parse_error:
            violations.append({"path": item.path, "issue": item.parse_error})
        for fn in item.functions:
            if fn.complexity > max_complexity:
                violations.append(
                    {
                        "path": item.path,
                        "issue": f"Function '{fn.name}' complexity {fn.complexity} > {max_complexity}",
                    }
                )
    return violations


def analyze_target(target_path: Path, max_complexity: int = 12) -> dict:
    """Analyze a file or directory and return structured AST & blast-radius telemetry."""
    base_dir = target_path.parent if target_path.is_file() else target_path
    analyses = [_scan_single_file(src_path, base_dir) for src_path in _iter_source_files(target_path)]

    _resolve_blast_radius(analyses)
    analyses.sort(key=lambda item: (-item.blast_radius_score, -item.max_complexity, item.path))
    violations = _collect_violations(analyses, max_complexity)

    return {
        "target": str(target_path),
        "max_complexity_gate": max_complexity,
        "summary": {
            "total_files": len(analyses),
            "total_loc": sum(a.loc for a in analyses),
            "total_functions": sum(len(a.functions) for a in analyses),
            "highest_complexity": max((a.max_complexity for a in analyses), default=0),
            "highest_blast_radius": max((a.blast_radius_score for a in analyses), default=0),
            "gate_violations": len(violations),
        },
        "violations": violations,
        "files": [asdict(item) for item in analyses],
    }


def format_markdown_report(report: dict) -> str:
    """Format analysis JSON into a concise Markdown engineering summary."""
    summary = report["summary"]
    lines = [
        "# Apex Code Architect — AST Blast-Radius Report",
        "",
        f"- **Target**: `{report['target']}`",
        f"- **Files Scanned**: {summary['total_files']} | **Total LOC**: {summary['total_loc']} | **Functions**: {summary['total_functions']}",
        f"- **Peak Complexity**: {summary['highest_complexity']} (Gate: <= {report['max_complexity_gate']})",
        f"- **Gate Violations**: {summary['gate_violations']}",
        "",
        "| Module | Lang | LOC | Functions | Max Complexity | Fan-In | Blast Score |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in report["files"]:
        fan_in = len(item["reverse_dependents"])
        lines.append(
            f"| `{item['path']}` | {item['language']} | {item['loc']} | {len(item['functions'])} | "
            f"{item['max_complexity']} | {fan_in} | {item['blast_radius_score']} |"
        )
    if report["violations"]:
        lines.extend(["", "## Gate Violations"])
        for v in report["violations"]:
            lines.append(f"- `{v['path']}`: {v['issue']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for AST blast-radius analysis."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Analyze AST complexity and blast radius.")
    parser.add_argument("target", help="File or repository directory to analyze")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--max-complexity", type=int, default=12)
    parser.add_argument("--strict", action="store_true", help="Exit 1 if gate violations exist")
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"Error: Target path does not exist: {target}", file=sys.stderr)
        return 2

    report = analyze_target(target, max_complexity=args.max_complexity)
    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_markdown_report(report))

    if args.strict and report["summary"]["gate_violations"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
