import ast
from pathlib import Path
import unittest

from app.migration import forward, rollback


class RollbackCoverageContract(unittest.TestCase):
    def test_migration_tests_include_real_rollback_behavior(self):
        test_file = Path(__file__).with_name("test_migration.py")
        source = test_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(test_file))

        for suite in tree.body:
            if not isinstance(suite, ast.ClassDef):
                continue
            for node in suite.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test"):
                    continue
                test_source = ast.get_source_segment(source, node) or ""
                rollback_line = self._rollback_after_forward_line(node)
                if rollback_line is None or not self._asserts_removed_column(node, test_source, rollback_line):
                    continue
                schema = {"columns": ["id"]}
                forward(schema, "email")
                self.assertIn("email", schema["columns"])
                rollback(schema, "email")
                self.assertNotIn("email", schema["columns"])
                return

        self.fail(
            "Add a rollback behavior test to tests/test_migration.py that calls "
            "forward(...) before rollback(...) and then asserts the column is removed from "
            "schema['columns']; do not edit this protected contract test."
        )

    def _rollback_after_forward_line(self, node):
        forward_lines = []
        rollback_lines = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name == "forward":
                forward_lines.append(child.lineno)
            elif name == "rollback":
                rollback_lines.append(child.lineno)
        return min((line for line in rollback_lines if any(prior < line for prior in forward_lines)), default=None)

    def _asserts_removed_column(self, node, source, rollback_line):
        if "schema" not in source or "columns" not in source:
            return False
        for child in ast.walk(node):
            if getattr(child, "lineno", 0) <= rollback_line:
                continue
            if isinstance(child, ast.Assert):
                if self._is_not_in_schema_columns_compare(child.test):
                    return True
                continue
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr == "assertNotIn" and len(child.args) >= 2:
                if self._references_schema_columns(child.args[1]):
                    return True
            if func.attr == "assertEqual" and len(child.args) >= 2:
                left, right = child.args[:2]
                if self._references_schema_columns(left) and self._is_columns_after_rollback(right):
                    return True
                if self._references_schema_columns(right) and self._is_columns_after_rollback(left):
                    return True
            if func.attr == "assertFalse" and child.args:
                if self._is_in_schema_columns_compare(child.args[0]):
                    return True
        return False

    def _is_not_in_schema_columns_compare(self, node):
        for child in ast.walk(node):
            if isinstance(child, ast.Compare):
                if any(isinstance(op, ast.NotIn) for op in child.ops):
                    if any(self._references_schema_columns(item) for item in child.comparators):
                        return True
        return False

    def _is_in_schema_columns_compare(self, node):
        for child in ast.walk(node):
            if isinstance(child, ast.Compare):
                if any(isinstance(op, ast.In) for op in child.ops):
                    if any(self._references_schema_columns(item) for item in child.comparators):
                        return True
        return False

    def _is_columns_after_rollback(self, node):
        if not isinstance(node, (ast.List, ast.Tuple)):
            return False
        values = []
        for item in node.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                return False
            values.append(item.value)
        return values == ["id"]

    def _references_schema_columns(self, node):
        for child in ast.walk(node):
            if not isinstance(child, ast.Subscript):
                continue
            if not isinstance(child.value, ast.Name) or child.value.id != "schema":
                continue
            key = child.slice
            if isinstance(key, ast.Constant) and key.value == "columns":
                return True
        return False


if __name__ == "__main__":
    unittest.main()
