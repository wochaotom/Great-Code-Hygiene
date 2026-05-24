"""Generated hygiene matrix target families."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
@dataclass
class MatrixCase:
    case_id: str
    family: str
    prompt_id: str
    category: str
    command: list[str]
    files: dict[str, str]
    fixed_files: dict[str, str]
    split: str = "train"
    evidence_kind: str = "candidate_evidence"
    generated: bool = True
@dataclass
class ReviewCase:
    case_id: str
    family: str
    prompt_id: str
    category: str
    visible_command: list[str]
    hidden_command: list[str]
    files: dict[str, str]
    fixed_files: dict[str, str]
    contracts: list[str]
    hidden_contracts: list[str]
    split: str = "holdout"
    evidence_kind: str = "candidate_evidence"
    generated: bool = True
def py_unittest() -> list[str]:
    return ["{python}", "-m", "unittest", "discover", "-s", "tests"]
def case(case_id, family, prompt_id, category, files, fixed, split="train", command=None):
    return MatrixCase(case_id, family, prompt_id, category, command or py_unittest(), files, fixed, split)
def review_case(case_id, family, prompt_id, category, files, fixed, contracts, hidden_contracts):
    return ReviewCase(case_id, family, prompt_id, category, py_unittest(), ["{python}", "-m", "unittest", "discover", "-s", "hidden_tests"], files, fixed, contracts, hidden_contracts)
def currency_case(i):
    price = ["0.29", "0.57", "0.58"][i % 3]
    qty = i + 2
    expected = int((Decimal(price) * qty * 100).to_integral_value())
    broken = 'def total_cents(unit_price, quantity):\n    return int(float(unit_price) * 100) * quantity\n'
    fixed = 'from decimal import Decimal, ROUND_HALF_UP\ndef total_cents(unit_price, quantity):\n    amount = Decimal(str(unit_price)) * Decimal(quantity)\n    return int((amount * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))\n'
    test = f'import unittest\nfrom app.pricing import total_cents\nclass PricingTests(unittest.TestCase):\n    def test_variant_total_cents(self):\n        self.assertEqual(total_cents("{price}", {qty}), {expected})\nif __name__ == "__main__":\n    unittest.main()\n'
    return case(f"currency-{i:04d}", "currency_rounding", "HYG-006", "Correctness and Regressions", {"app/__init__.py": "", "app/pricing.py": broken, "tests/test_pricing.py": test}, {"app/pricing.py": fixed})
def sql_case(i):
    role, admin = f"user_{i}", f"admin_{i}"
    broken = 'def usernames_by_role(conn, role):\n    rows = conn.execute(\n        f"SELECT username FROM users WHERE role = \'{role}\' ORDER BY username"\n    ).fetchall()\n    return [row[0] for row in rows]\n'
    fixed = 'def usernames_by_role(conn, role):\n    rows = conn.execute(\n        "SELECT username FROM users WHERE role = ? ORDER BY username",\n        (role,),\n    ).fetchall()\n    return [row[0] for row in rows]\n'
    test = f'import sqlite3\nimport unittest\nfrom app.users import usernames_by_role\nclass UserQueryTests(unittest.TestCase):\n    def make_conn(self):\n        conn = sqlite3.connect(":memory:")\n        conn.execute("CREATE TABLE users (username TEXT, role TEXT)")\n        conn.executemany("INSERT INTO users (username, role) VALUES (?, ?)", [("alice", "{role}"), ("root", "{admin}")])\n        self.addCleanup(conn.close)\n        return conn\n    def test_returns_matching_role(self):\n        self.assertEqual(usernames_by_role(self.make_conn(), "{role}"), ["alice"])\n    def test_injected_role_does_not_return_other_roles(self):\n        self.assertEqual(usernames_by_role(self.make_conn(), "{role}\' OR role = \'{admin}"), [])\nif __name__ == "__main__":\n    unittest.main()\n'
    return case(f"sql-{i:04d}", "sql_parameters", "HYG-031", "Security and Data Safety", {"app/__init__.py": "", "app/users.py": broken, "tests/test_users.py": test}, {"app/users.py": fixed})
def retry_case(i):
    attempts = i % 5 + 2
    broken = 'async function callWithRetry(operation, options = {}) {\n  const maxAttempts = options.maxAttempts ?? 3;\n  let lastError;\n  for (let attempt = 0; attempt <= maxAttempts; attempt += 1) {\n    try { return await operation(); } catch (error) { lastError = error; }\n  }\n  throw lastError;\n}\nmodule.exports = { callWithRetry };\n'
    fixed = broken.replace("attempt <= maxAttempts", "attempt < maxAttempts")
    test = f'const assert = require("node:assert/strict");\nconst test = require("node:test");\nconst {{ callWithRetry }} = require("../app/retry");\ntest("stops after max attempts", async () => {{\n  let calls = 0;\n  await assert.rejects(callWithRetry(async () => {{ calls += 1; throw new Error("temporary-{i}"); }}, {{ maxAttempts: {attempts} }}), /temporary-{i}/);\n  assert.equal(calls, {attempts});\n}});\ntest("still succeeds after transient failures", async () => {{\n  let calls = 0;\n  const result = await callWithRetry(async () => {{ calls += 1; if (calls < {attempts}) throw new Error("temporary-{i}"); return "ok-{i}"; }}, {{ maxAttempts: {attempts} }});\n  assert.equal(result, "ok-{i}");\n  assert.equal(calls, {attempts});\n}});\n'
    return case(f"retry-{i:04d}", "retry_bounds_js", "HYG-062", "Error Handling and Observability", {"app/retry.js": broken, "tests/retry.test.js": test}, {"app/retry.js": fixed}, command=["node", "--test", "tests/retry.test.js"])
def secret_log_case(i):
    key = ["api_token", "password", "client_secret", "access_key"][i % 4]
    secret = f"secret-{i}"
    broken = 'def failure_log(error, context):\n    payload = {"level": "error", "message": str(error)}\n    payload.update(context)\n    return payload\n'
    fixed = 'SENSITIVE_KEY_PARTS = ("password", "secret", "token", "key")\ndef failure_log(error, context):\n    payload = {"level": "error", "message": str(error)}\n    for key, value in context.items():\n        lowered = str(key).lower()\n        payload[key] = "[REDACTED]" if any(part in lowered for part in SENSITIVE_KEY_PARTS) else value\n    return payload\n'
    test = f'import json\nimport unittest\nfrom app.logging_helpers import failure_log\nclass FailureLogTests(unittest.TestCase):\n    def test_redacts_secret_but_keeps_context(self):\n        record = failure_log(RuntimeError("upstream timeout"), {{"request_id": "req-{i}", "operation": "sync", "{key}": "{secret}"}})\n        self.assertEqual(record["request_id"], "req-{i}")\n        self.assertEqual(record["operation"], "sync")\n        self.assertNotIn("{secret}", json.dumps(record, sort_keys=True))\nif __name__ == "__main__":\n    unittest.main()\n'
    return case(f"secret-log-{i:04d}", "secret_safe_logs", "HYG-064", "Error Handling and Observability", {"app/__init__.py": "", "app/logging_helpers.py": broken, "tests/test_logging_helpers.py": test}, {"app/logging_helpers.py": fixed})
def config_case(i):
    file_timeout, env_timeout = i + 10, i + 3
    broken = 'def load_config(file_config=None, env=None):\n    env = env or {}\n    config = {"timeout": 30, "endpoint": "http://localhost"}\n    if "APP_TIMEOUT" in env:\n        config["timeout"] = int(env["APP_TIMEOUT"])\n    if file_config:\n        config.update(file_config)\n    return config\n'
    fixed = 'def load_config(file_config=None, env=None):\n    env = env or {}\n    config = {"timeout": 30, "endpoint": "http://localhost"}\n    if file_config:\n        config.update(file_config)\n    if "APP_TIMEOUT" in env:\n        config["timeout"] = int(env["APP_TIMEOUT"])\n    return config\n'
    test = f'import unittest\nfrom app.config import load_config\nclass ConfigTests(unittest.TestCase):\n    def test_defaults_and_file_config_still_work(self):\n        self.assertEqual(load_config()["timeout"], 30)\n        self.assertEqual(load_config({{"timeout": {file_timeout}}})["timeout"], {file_timeout})\n    def test_environment_overrides_file_config(self):\n        self.assertEqual(load_config({{"timeout": {file_timeout}}}, {{"APP_TIMEOUT": "{env_timeout}"}})["timeout"], {env_timeout})\nif __name__ == "__main__":\n    unittest.main()\n'
    return case(f"config-{i:04d}", "config_precedence", "HYG-083", "Dependency and Config Hygiene", {"app/__init__.py": "", "app/config.py": broken, "tests/test_config.py": test}, {"app/config.py": fixed})
def parser_case(i):
    raw = f" alpha_{i}, beta_{i},, Gamma_{i} "
    expected = [f"alpha_{i}", f"beta_{i}", f"gamma_{i}"]
    broken = "def parse_tags(text):\n    return text.split(',')\n"
    fixed = "def parse_tags(text):\n    return [part.strip().lower() for part in text.split(',') if part.strip()]\n"
    test = f'import unittest\nfrom app.parser import parse_tags\nclass ParserTests(unittest.TestCase):\n    def test_trims_lowercases_and_drops_empty_tags(self):\n        self.assertEqual(parse_tags("{raw}"), {expected!r})\nif __name__ == "__main__":\n    unittest.main()\n'
    return case(f"parser-{i:04d}", "parser_edges", "HYG-016", "Test Quality", {"app/__init__.py": "", "app/parser.py": broken, "tests/test_parser.py": test}, {"app/parser.py": fixed})
def api_auth_case(i):
    tenant = f"tenant-{i}"
    other = f"tenant-{i + 1}"
    broken = 'def can_update(actor, resource):\n    return actor["id"] == resource["owner_id"] or actor.get("role") == "admin"\n'
    fixed = 'def can_update(actor, resource):\n    same_tenant = actor.get("tenant_id") == resource.get("tenant_id")\n    return same_tenant and (actor["id"] == resource["owner_id"] or actor.get("role") == "admin")\n'
    test = f'import unittest\nfrom app.authz import can_update\nclass AuthzTests(unittest.TestCase):\n    def test_owner_in_same_tenant_can_update(self):\n        self.assertTrue(can_update({{"id": "u{i}", "tenant_id": "{tenant}", "role": "user"}}, {{"owner_id": "u{i}", "tenant_id": "{tenant}"}}))\n    def test_cross_tenant_admin_is_rejected(self):\n        self.assertFalse(can_update({{"id": "root", "tenant_id": "{other}", "role": "admin"}}, {{"owner_id": "u{i}", "tenant_id": "{tenant}"}}))\nif __name__ == "__main__":\n    unittest.main()\n'
    return case(f"api-auth-{i:04d}", "api_authorization", "HYG-034", "Security and Data Safety", {"app/__init__.py": "", "app/authz.py": broken, "tests/test_authz.py": test}, {"app/authz.py": fixed})
def platform_path_case(i):
    filename = f"report_{i}.txt"
    broken = "def basename(path):\n    return str(path).split('/')[-1]\n"
    fixed = "from pathlib import PurePosixPath, PureWindowsPath\ndef basename(path):\n    text = str(path)\n    return PureWindowsPath(text).name if '\\\\' in text else PurePosixPath(text).name\n"
    test = f'import unittest\nfrom app.paths import basename\nclass PathTests(unittest.TestCase):\n    def test_windows_and_posix_paths(self):\n        self.assertEqual(basename("C:\\\\tmp\\\\{filename}"), "{filename}")\n        self.assertEqual(basename("/tmp/{filename}"), "{filename}")\nif __name__ == "__main__":\n    unittest.main()\n'
    return case(f"platform-path-{i:04d}", "platform_paths", "HYG-089", "Dependency and Config Hygiene", {"app/__init__.py": "", "app/paths.py": broken, "tests/test_paths.py": test}, {"app/paths.py": fixed})
def html_case(i):
    text = f"<script>alert({i})</script>"
    broken = "def render_comment(text):\n    return f'<p>{text}</p>'\n"
    fixed = "from html import escape\ndef render_comment(text):\n    return f'<p>{escape(text)}</p>'\n"
    test = f'import unittest\nfrom app.comments import render_comment\nclass CommentRenderTests(unittest.TestCase):\n    def test_escapes_user_content(self):\n        html = render_comment("{text}")\n        self.assertNotIn("<script>", html)\n        self.assertIn("&lt;script&gt;", html)\nif __name__ == "__main__":\n    unittest.main()\n'
    return case(f"html-{i:04d}", "html_escaping_holdout", "HYG-036", "Security and Data Safety", {"app/__init__.py": "", "app/comments.py": broken, "tests/test_comments.py": test}, {"app/comments.py": fixed}, split="holdout")
def migration_case(i):
    col = f"flag_{i}"
    broken = "def forward(schema, column):\n    schema.append(column)\ndef rollback(schema, column):\n    return schema\n"
    fixed = "def forward(schema, column):\n    if column not in schema:\n        schema.append(column)\ndef rollback(schema, column):\n    if column in schema:\n        schema.remove(column)\n    return schema\n"
    test = f'import unittest\nfrom app.migration import forward, rollback\nclass MigrationTests(unittest.TestCase):\n    def test_forward_and_rollback(self):\n        schema = ["id"]\n        forward(schema, "{col}")\n        self.assertIn("{col}", schema)\n        rollback(schema, "{col}")\n        self.assertNotIn("{col}", schema)\nif __name__ == "__main__":\n    unittest.main()\n'
    return case(f"migration-{i:04d}", "migration_rollback_holdout", "HYG-019", "Test Quality", {"app/__init__.py": "", "app/migration.py": broken, "tests/test_migration.py": test}, {"app/migration.py": fixed}, split="holdout")
def docs_case(i):
    option = f"--new-{i}"
    broken = f'DOCS = "Usage: tool --old-{i}"\nOPTIONS = ["{option}"]\ndef usage_text():\n    return DOCS\n'
    fixed = f'OPTIONS = ["{option}"]\ndef usage_text():\n    return "Usage: tool " + " ".join(OPTIONS)\n'
    test = f'import unittest\nfrom app.docs import usage_text\nclass DocsTests(unittest.TestCase):\n    def test_docs_match_current_option(self):\n        text = usage_text()\n        self.assertIn("{option}", text)\n        self.assertNotIn("--old-{i}", text)\nif __name__ == "__main__":\n    unittest.main()\n'
    return case(f"docs-{i:04d}", "docs_staleness_holdout", "HYG-080", "Documentation and Comments", {"app/__init__.py": "", "app/docs.py": broken, "tests/test_docs.py": test}, {"app/docs.py": fixed}, split="holdout")
def dependency_case(i):
    package = f"leftpad{i}"
    broken = f'def choose_parser(existing):\n    return "{package}"\n'
    fixed = 'def choose_parser(existing):\n    return "json" if "json" in existing else None\n'
    test = f'import unittest\nfrom app.dependencies import choose_parser\nclass DependencyTests(unittest.TestCase):\n    def test_reuses_standard_library_parser(self):\n        self.assertEqual(choose_parser(["json"]), "json")\n        self.assertNotEqual(choose_parser(["json"]), "{package}")\nif __name__ == "__main__":\n    unittest.main()\n'
    return case(f"dependency-{i:04d}", "dependency_avoidance_holdout", "HYG-081", "Dependency and Config Hygiene", {"app/__init__.py": "", "app/dependencies.py": broken, "tests/test_dependencies.py": test}, {"app/dependencies.py": fixed}, split="holdout")
def claims_review_case(i):
    spec = "# Contract\n- C-EXP: reject expired claims.\n- C-NBF: reject claims before nbf.\n- C-AUD: require aud to include the requested audience.\n"
    broken = 'def is_authorized(claims, now, audience):\n    return claims.get("exp", 0) > now\n'
    fixed = 'def is_authorized(claims, now, audience):\n    if claims.get("exp", 0) <= now:\n        return False\n    if claims.get("nbf", now) > now:\n        return False\n    claim_aud = claims.get("aud")\n    if isinstance(claim_aud, str):\n        return claim_aud == audience\n    if isinstance(claim_aud, list):\n        return audience in claim_aud\n    return False\n'
    visible = 'import unittest\nfrom app.claims import is_authorized\nclass ClaimsTests(unittest.TestCase):\n    def test_expiration_with_audience(self):\n        self.assertTrue(is_authorized({"exp": 200, "aud": "api"}, 100, "api"))\n        self.assertFalse(is_authorized({"exp": 50, "aud": "api"}, 100, "api"))\nif __name__ == "__main__":\n    unittest.main()\n'
    hidden = 'import unittest\nfrom app.claims import is_authorized\nclass HiddenClaimsTests(unittest.TestCase):\n    def test_not_before_and_audience(self):\n        self.assertFalse(is_authorized({"exp": 200, "nbf": 150, "aud": "api"}, 100, "api"))\n        self.assertFalse(is_authorized({"exp": 200, "nbf": 50, "aud": "web"}, 100, "api"))\n        self.assertTrue(is_authorized({"exp": 200, "nbf": 50, "aud": ["web", "api"]}, 100, "api"))\n    def test_missing_audience_rejected(self):\n        self.assertFalse(is_authorized({"exp": 200}, 100, "api"))\nif __name__ == "__main__":\n    unittest.main()\n'
    return review_case(f"review-claims-{i:04d}", "review_claims_contract", "HYG-034", "Security and Data Safety", {"SPEC.md": spec, "app/__init__.py": "", "app/claims.py": broken, "tests/test_claims.py": visible, "hidden_tests/test_claims_hidden.py": hidden}, {"app/claims.py": fixed}, ["C-EXP", "C-NBF", "C-AUD"], ["C-NBF", "C-AUD"])
def path_review_case(i):
    spec = "# Contract\n- P-ROOT: resolved paths must stay inside root.\n- P-ABS: absolute requested paths are rejected.\n- P-PREFIX: sibling prefix escapes are rejected.\n"
    broken = 'import os\ndef safe_join(root, requested):\n    candidate = os.path.normpath(os.path.join(root, requested))\n    if not candidate.startswith(root):\n        raise ValueError("outside root")\n    return candidate\n'
    fixed = 'from pathlib import Path\ndef safe_join(root, requested):\n    root_path = Path(root).resolve()\n    candidate = (root_path / requested).resolve()\n    try:\n        candidate.relative_to(root_path)\n    except ValueError as exc:\n        raise ValueError("outside root") from exc\n    return str(candidate)\n'
    visible = 'import tempfile\nimport unittest\nfrom pathlib import Path\nfrom app.safe_paths import safe_join\nclass SafePathTests(unittest.TestCase):\n    def test_inside_path(self):\n        with tempfile.TemporaryDirectory() as tmp:\n            self.assertEqual(Path(safe_join(tmp, "reports/today.txt")).name, "today.txt")\nif __name__ == "__main__":\n    unittest.main()\n'
    hidden = 'import tempfile\nimport unittest\nfrom pathlib import Path\nfrom app.safe_paths import safe_join\nclass HiddenSafePathTests(unittest.TestCase):\n    def test_sibling_prefix_escape_rejected(self):\n        with tempfile.TemporaryDirectory() as parent:\n            root = Path(parent) / "app"\n            root.mkdir()\n            with self.assertRaises(ValueError):\n                safe_join(str(root), "../app_evil/secret.txt")\n    def test_absolute_escape_rejected(self):\n        with tempfile.TemporaryDirectory() as parent:\n            root = Path(parent) / "root"\n            root.mkdir()\n            with self.assertRaises(ValueError):\n                safe_join(str(root), str(Path(parent) / "other.txt"))\nif __name__ == "__main__":\n    unittest.main()\n'
    return review_case(f"review-path-{i:04d}", "review_path_containment", "HYG-032", "Security and Data Safety", {"SPEC.md": spec, "app/__init__.py": "", "app/safe_paths.py": broken, "tests/test_safe_paths.py": visible, "hidden_tests/test_safe_paths_hidden.py": hidden}, {"app/safe_paths.py": fixed}, ["P-ROOT", "P-ABS", "P-PREFIX"], ["P-ABS", "P-PREFIX"])
def unicode_review_case(i):
    spec = "# Contract\n- U-NFKC: normalize usernames with NFKC.\n- U-CASEFOLD: use Unicode casefolding.\n- U-NONEMPTY: reject empty usernames after normalization.\n"
    broken = "def canonical_username(value):\n    return value.strip().lower()\n"
    fixed = 'import unicodedata\ndef canonical_username(value):\n    normalized = unicodedata.normalize("NFKC", value).strip().casefold()\n    if not normalized:\n        raise ValueError("username must not be empty")\n    return normalized\n'
    visible = 'import unittest\nfrom app.users import canonical_username\nclass UserTests(unittest.TestCase):\n    def test_basic_normalization(self):\n        self.assertEqual(canonical_username(" Alice "), "alice")\nif __name__ == "__main__":\n    unittest.main()\n'
    hidden = 'import unittest\nfrom app.users import canonical_username\nclass HiddenUserTests(unittest.TestCase):\n    def test_nfkc_and_casefold(self):\n        self.assertEqual(canonical_username(" \\uFF21\\uFF2C\\uFF29\\uFF23\\uFF25 "), "alice")\n        self.assertEqual(canonical_username("Stra\\u00dfe"), "strasse")\n    def test_rejects_empty_after_trim(self):\n        with self.assertRaises(ValueError):\n            canonical_username("   ")\nif __name__ == "__main__":\n    unittest.main()\n'
    return review_case(f"review-unicode-{i:04d}", "review_unicode_username", "HYG-016", "Correctness and Regressions", {"SPEC.md": spec, "app/__init__.py": "", "app/users.py": broken, "tests/test_users.py": visible, "hidden_tests/test_users_hidden.py": hidden}, {"app/users.py": fixed}, ["U-NFKC", "U-CASEFOLD", "U-NONEMPTY"], ["U-NFKC", "U-CASEFOLD", "U-NONEMPTY"])
def cache_review_case(i):
    spec = "# Contract\n- K-REUSE: reuse cache entries for the same tenant and user.\n- K-TENANT: tenant_id is part of the cache key.\n"
    broken = "def get_profile(cache, db, user_id, tenant_id):\n    if user_id not in cache:\n        cache[user_id] = db.fetch_profile(user_id, tenant_id)\n    return cache[user_id]\n"
    fixed = "def get_profile(cache, db, user_id, tenant_id):\n    key = (tenant_id, user_id)\n    if key not in cache:\n        cache[key] = db.fetch_profile(user_id, tenant_id)\n    return cache[key]\n"
    visible = 'import unittest\nfrom app.cache import get_profile\nclass Db:\n    def __init__(self): self.calls = 0\n    def fetch_profile(self, user_id, tenant_id):\n        self.calls += 1\n        return {"user_id": user_id, "tenant_id": tenant_id}\nclass CacheTests(unittest.TestCase):\n    def test_reuses_same_user_profile(self):\n        cache = {}; db = Db()\n        self.assertEqual(get_profile(cache, db, "u1", "t1")["tenant_id"], "t1")\n        self.assertEqual(get_profile(cache, db, "u1", "t1")["tenant_id"], "t1")\n        self.assertEqual(db.calls, 1)\nif __name__ == "__main__":\n    unittest.main()\n'
    hidden = 'import unittest\nfrom app.cache import get_profile\nclass Db:\n    def __init__(self): self.calls = []\n    def fetch_profile(self, user_id, tenant_id):\n        self.calls.append((user_id, tenant_id))\n        return {"user_id": user_id, "tenant_id": tenant_id}\nclass HiddenCacheTests(unittest.TestCase):\n    def test_tenant_is_part_of_cache_key(self):\n        cache = {}; db = Db()\n        self.assertEqual(get_profile(cache, db, "u1", "t1")["tenant_id"], "t1")\n        self.assertEqual(get_profile(cache, db, "u1", "t2")["tenant_id"], "t2")\n        self.assertEqual(db.calls, [("u1", "t1"), ("u1", "t2")])\nif __name__ == "__main__":\n    unittest.main()\n'
    return review_case(f"review-cache-{i:04d}", "review_cache_scope", "HYG-083", "Security and Data Safety", {"SPEC.md": spec, "app/__init__.py": "", "app/cache.py": broken, "tests/test_cache.py": visible, "hidden_tests/test_cache_hidden.py": hidden}, {"app/cache.py": fixed}, ["K-REUSE", "K-TENANT"], ["K-TENANT"])
FAMILIES = {
    "currency": currency_case,
    "sql": sql_case,
    "retry": retry_case,
    "logs": secret_log_case,
    "config": config_case,
    "parser": parser_case,
    "api_auth": api_auth_case,
    "platform_path": platform_path_case,
    "html": html_case,
    "migration": migration_case,
    "docs": docs_case,
    "dependency": dependency_case,
}
REVIEW_FAMILIES = {
    "claims": claims_review_case,
    "path": path_review_case,
    "unicode": unicode_review_case,
    "cache": cache_review_case,
}
def family_split(name: str) -> str:
    return FAMILIES[name](0).split
def family_names(split: str = "train") -> list[str]:
    names = sorted(FAMILIES)
    if split == "all":
        return names
    return [name for name in names if family_split(name) == split]
def family_manifest() -> list[dict]:
    return [
        {
            "name": name,
            "split": family_split(name),
            "family": FAMILIES[name](0).family,
            "evidence_kind": FAMILIES[name](0).evidence_kind,
            "generated": FAMILIES[name](0).generated,
        }
        for name in sorted(FAMILIES)
    ]
def review_family_manifest() -> list[dict]:
    return [
        {
            "name": name,
            "split": REVIEW_FAMILIES[name](0).split,
            "family": REVIEW_FAMILIES[name](0).family,
            "evidence_kind": REVIEW_FAMILIES[name](0).evidence_kind,
            "generated": REVIEW_FAMILIES[name](0).generated,
        }
        for name in sorted(REVIEW_FAMILIES)
    ]
def build_cases(families: list[str], variants_per_family: int, start_index: int = 0) -> list[MatrixCase]:
    cases: list[MatrixCase] = []
    for family in families:
        factory = FAMILIES[family]
        for index in range(start_index, start_index + variants_per_family):
            cases.append(factory(index))
    return cases
def build_review_cases(families: list[str], variants_per_family: int, start_index: int = 0) -> list[ReviewCase]:
    cases: list[ReviewCase] = []
    for family in families:
        factory = REVIEW_FAMILIES[family]
        for index in range(start_index, start_index + variants_per_family):
            cases.append(factory(index))
    return cases
