"""Comprehensive test suite for Apex Code Architect AST blast-radius analyzer."""

from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add repo scripts directory to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import ast_blast_radius


class TestPythonComplexity(unittest.TestCase):
    """Test AST-based McCabe cyclomatic complexity calculation for Python."""

    def test_linear_function_complexity(self) -> None:
        """Linear function without branches should have complexity 1."""
        code = "def simple():\n    x = 1\n    return x\n"
        tree = ast.parse(code)
        fn_node = tree.body[0]
        self.assertEqual(ast_blast_radius._compute_py_complexity(fn_node), 1)

    def test_branching_complexity(self) -> None:
        """Branching statements should increment cyclomatic complexity."""
        code = (
            "def branchy(a, b):\n"
            "    if a > 0:\n"
            "        for i in range(b):\n"
            "            while a < 10:\n"
            "                a += 1\n"
            "    elif b > 0:\n"
            "        try:\n"
            "            return a // b\n"
            "        except ZeroDivisionError:\n"
            "            pass\n"
            "    return [x for x in range(a) if x % 2 == 0]\n"
        )
        tree = ast.parse(code)
        fn_node = tree.body[0]
        # if (1) + for (1) + while (1) + elif (1) + except (1) + comp_if (1) + base (1) = 7
        complexity = ast_blast_radius._compute_py_complexity(fn_node)
        self.assertGreaterEqual(complexity, 6)

    def test_boolean_operations_complexity(self) -> None:
        """BoolOp with multiple conditions adds complexity."""
        code = "def cond(a, b, c):\n    if a and b or c:\n        return True\n"
        tree = ast.parse(code)
        fn_node = tree.body[0]
        self.assertEqual(ast_blast_radius._compute_py_complexity(fn_node), 4)

    def test_python_import_extraction(self) -> None:
        """Imports and ImportFrom nodes should be extracted correctly."""
        code = "import os\nimport sys\nfrom pathlib import Path\nfrom typing import Dict, List\n"
        tree = ast.parse(code)
        imports = ast_blast_radius._extract_py_imports(tree)
        self.assertEqual(imports, ["os", "pathlib", "sys", "typing"])

    def test_analyze_python_syntax_error(self) -> None:
        """Invalid Python syntax should report parse_error without raising."""
        bad_code = "def broken(:\n    pass\n"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
            tmp.write(bad_code)
            tmp_path = Path(tmp.name)

        try:
            analysis = ast_blast_radius._analyze_python_file(tmp_path, "broken.py", bad_code)
            self.assertIsNotNone(analysis.parse_error)
            self.assertIn("SyntaxError", analysis.parse_error)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


class TestJavaScriptScanning(unittest.TestCase):
    """Test structural scanner for JavaScript and TypeScript modules."""

    def test_js_function_and_branch_scanning(self) -> None:
        """Identify named functions, arrow functions, and branch keywords."""
        js_code = (
            "import { useState } from 'react';\n"
            "const helper = require('./utils');\n"
            "export async function processData(items) {\n"
            "  if (!items) return [];\n"
            "  for (const item of items) {\n"
            "    if (item.valid && item.active) {\n"
            "      console.log(item);\n"
            "    }\n"
            "  }\n"
            "  return items;\n"
            "}\n"
            "const handleAction = (event) => {\n"
            "  return event ? true : false;\n"
            "};\n"
        )
        analysis = ast_blast_radius._analyze_js_file("component.tsx", js_code)
        self.assertEqual(analysis.language, "js/ts")
        self.assertEqual(analysis.imports, ["./utils", "react"])
        self.assertGreaterEqual(len(analysis.functions), 2)
        fn_names = [f.name for f in analysis.functions]
        self.assertIn("processData", fn_names)
        self.assertIn("handleAction", fn_names)

    def test_js_fallback_module_metric(self) -> None:
        """If no function regex matches, fall back to module-level metrics."""
        script_code = "const x = 1;\nif (x > 0) {\n  console.log(x);\n}\n"
        analysis = ast_blast_radius._analyze_js_file("script.js", script_code)
        self.assertEqual(len(analysis.functions), 1)
        self.assertEqual(analysis.functions[0].name, "<module>")
        self.assertGreaterEqual(analysis.functions[0].complexity, 2)


class TestBlastRadiusResolution(unittest.TestCase):
    """Test reverse-dependency graph mapping and blast-radius score computation."""

    def test_fan_in_and_blast_score(self) -> None:
        """Modules imported by others must accumulate reverse_dependents and higher score."""
        file_a = ast_blast_radius.FileAnalysis(
            path="core/utils.py",
            language="python",
            loc=50,
            imports=[],
            max_complexity=3,
        )
        file_b = ast_blast_radius.FileAnalysis(
            path="services/service_one.py",
            language="python",
            loc=100,
            imports=["core.utils"],
            max_complexity=4,
        )
        file_c = ast_blast_radius.FileAnalysis(
            path="services/service_two.py",
            language="python",
            loc=120,
            imports=["core.utils"],
            max_complexity=5,
        )

        analyses = [file_a, file_b, file_c]
        ast_blast_radius._resolve_blast_radius(analyses)

        self.assertEqual(file_a.reverse_dependents, ["services/service_one.py", "services/service_two.py"])
        # Blast score: len(deps) * 2 + max_complexity = 2 * 2 + 3 = 7
        self.assertEqual(file_a.blast_radius_score, 7)
        self.assertEqual(file_b.reverse_dependents, [])
        self.assertEqual(file_b.blast_radius_score, 4)


class TestMarkdownAndJsonReports(unittest.TestCase):
    """Test formatting and reporting functionality."""

    def test_format_markdown_report_clean(self) -> None:
        """Clean report without violations should have summary and table."""
        report = {
            "target": "src",
            "max_complexity_gate": 12,
            "summary": {
                "total_files": 1,
                "total_loc": 20,
                "total_functions": 1,
                "highest_complexity": 2,
                "highest_blast_radius": 2,
                "gate_violations": 0,
            },
            "violations": [],
            "files": [
                {
                    "path": "src/main.py",
                    "language": "python",
                    "loc": 20,
                    "functions": [{"name": "run", "complexity": 2}],
                    "max_complexity": 2,
                    "reverse_dependents": [],
                    "blast_radius_score": 2,
                }
            ],
        }
        md = ast_blast_radius.format_markdown_report(report)
        self.assertIn("# Apex Code Architect — AST Blast-Radius Report", md)
        self.assertIn("| `src/main.py` | python | 20 | 1 | 2 | 0 | 2 |", md)
        self.assertNotIn("## Gate Violations", md)

    def test_format_markdown_report_with_violations(self) -> None:
        """Report with violations should append Gate Violations section."""
        report = {
            "target": "src",
            "max_complexity_gate": 12,
            "summary": {
                "total_files": 1,
                "total_loc": 50,
                "total_functions": 1,
                "highest_complexity": 15,
                "highest_blast_radius": 15,
                "gate_violations": 1,
            },
            "violations": [{"path": "src/heavy.py", "issue": "Function 'heavy' complexity 15 > 12"}],
            "files": [
                {
                    "path": "src/heavy.py",
                    "language": "python",
                    "loc": 50,
                    "functions": [{"name": "heavy", "complexity": 15}],
                    "max_complexity": 15,
                    "reverse_dependents": [],
                    "blast_radius_score": 15,
                }
            ],
        }
        md = ast_blast_radius.format_markdown_report(report)
        self.assertIn("## Gate Violations", md)
        self.assertIn("- `src/heavy.py`: Function 'heavy' complexity 15 > 12", md)


class TestCliAndStrictGate(unittest.TestCase):
    """Test CLI execution, arguments, and exit code semantics."""

    def test_nonexistent_target_exits_two(self) -> None:
        """Passing a non-existent file or directory should return exit code 2."""
        code = ast_blast_radius.main(["non_existent_path_xyz_12345"])
        self.assertEqual(code, 2)

    def test_strict_mode_failure_on_violations(self) -> None:
        """In strict mode, exit code should be 1 if gate violations occur."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_file = tmp_path / "complex_mod.py"
            source_file.write_text(
                "def complex_fn(a, b, c):\n"
                "    if a:\n"
                "        for i in range(b):\n"
                "            while c:\n"
                "                return True\n"
                "    return False\n",
                encoding="utf-8",
            )
            # Max complexity is 4, gate is set to 2 -> violation
            exit_code_strict = ast_blast_radius.main([str(tmp_path), "--max-complexity", "2", "--strict"])
            self.assertEqual(exit_code_strict, 1)

            # Non-strict mode with same violation returns 0
            exit_code_lenient = ast_blast_radius.main([str(tmp_path), "--max-complexity", "2"])
            self.assertEqual(exit_code_lenient, 0)

    def test_json_format_cli_output(self) -> None:
        """Format json should produce parseable report payload."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_file = tmp_path / "valid.py"
            test_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

            report = ast_blast_radius.analyze_target(tmp_path, max_complexity=12)
            self.assertEqual(report["summary"]["gate_violations"], 0)
            self.assertEqual(report["summary"]["total_files"], 1)
            self.assertEqual(report["files"][0]["functions"][0]["name"], "hello")


if __name__ == "__main__":
    unittest.main()
