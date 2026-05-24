import ast
from pathlib import Path
import unittest


class RollbackCoverageContract(unittest.TestCase):
    def test_migration_tests_include_real_rollback_behavior(self):
        test_file = Path(__file__).with_name("test_migration.py")
        source = test_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(test_file))

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue
            test_source = ast.get_source_segment(source, node) or ""
            if not self._calls_rollback(node):
                continue
            if self._asserts_removed_column(node, test_source):
                return

        self.fail(
            "Add a rollback behavior test to tests/test_migration.py that calls "
            "rollback(...) and asserts the rolled-back column is removed from "
            "schema['columns']; do not edit this protected contract test."
        )

    def _calls_rollback(self, node):
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if isinstance(func, ast.Name) and func.id == "rollback":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "rollback":
                return True
        return False

    def _asserts_removed_column(self, node, source):
        if "schema" not in source or "columns" not in source:
            return False
        for child in ast.walk(node):
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
