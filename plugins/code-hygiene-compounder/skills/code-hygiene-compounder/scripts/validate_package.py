#!/usr/bin/env python3
"""Validate the Code Hygiene Compounder packaging workspace."""
from __future__ import annotations
import argparse
import fnmatch
import hashlib
import json
import os
import sys
from pathlib import Path
sys.dont_write_bytecode = True
from export_claude_package import COMMAND_TEXT
from export_claude_package import EXCLUDED_NAMES
from export_claude_package import build_portable_prompt
from export_claude_package import read_skill_text
from source_audit_plan import context_index_errors
PACKAGE_DIRS = {'codex_skill': Path('code-hygiene-compounder'), 'codex_plugin_skill': Path('plugins/code-hygiene-compounder/skills/code-hygiene-compounder'), 'claude_ai_skill': Path('code-hygiene-compounder-claude-ai/code-hygiene-compounder'), 'claude_command_package': Path('code-hygiene-compounder-command/.claude/code-hygiene-compounder')}
EXPECTED_NATIVE_AI_SKILL_FILES = {Path('.agents/skills/code-hygiene/SKILL.md'), Path('.cursor/skills/code-hygiene/SKILL.md')}
EXPECTED_SKILL_FILES = {Path('code-hygiene/SKILL.md'), Path('code-hygiene-skeleton/SKILL.md'), Path('code-hygiene-compounder/SKILL.md'), Path('code-hygiene-compounder-claude-ai/code-hygiene-compounder/SKILL.md'), Path('plugins/code-hygiene-compounder/skills/code-hygiene-compounder/SKILL.md')} | EXPECTED_NATIVE_AI_SKILL_FILES
EXPECTED_COMMAND_FILES = {Path('code-hygiene-compounder-command/.claude/commands/code-hygiene.md')}
EXPECTED_CURSOR_RULE_FILES = {Path('.cursor/rules/code-hygiene.mdc')}
EXPECTED_AGENT_FILES = {Path('code-hygiene-compounder/agents/openai.yaml')}
EXPECTED_INSTALL_FILES = {Path('code-hygiene-compounder-command/INSTALL.txt')}
EXPECTED_PROMPTS = {Path('portable-prompts/code-hygiene-compounder-chat.md')}
EXPECTED_CHATBOT_FILES = {Path('chatbot-profiles/README.md'), Path('chatbot-profiles/chatgpt-gpt-instructions.md'), Path('chatbot-profiles/claude-project-instructions.md'), Path('chatbot-profiles/gemini-gem-instructions.md')}
EXPECTED_PLUGIN_FILES = {Path('.agents/plugins/marketplace.json'), Path('.claude-plugin/marketplace.json'), Path('code-hygiene-compounder/.claude-plugin/plugin.json'), Path('plugins/code-hygiene-compounder/.codex-plugin/plugin.json')}
EXPECTED_CONTEXT_FILES = {Path('code-hygiene-compounder/references/context-index.json'), Path('code-hygiene-compounder/references/context-index.schema.json')}
MARKETPLACE_NAME = 'great-code-hygiene'
PLUGIN_NAME = 'code-hygiene-compounder'
CODEX_PLUGIN_SOURCE = './plugins/code-hygiene-compounder'
CODEX_PLUGIN_VERSION = '0.1.0'
PLUGIN_SOURCE = './code-hygiene-compounder'
PLUGIN_REPOSITORY = 'https://github.com/wochaotom/Great-Code-Hygiene'
OPENAI_AGENT_REQUIRED_SNIPPETS = ('deterministic feedback loops', 'PASS-100')
COMMAND_REQUIRED_SNIPPETS = ('smallest deterministic feedback loop', 'evidence-report.md', 'Do not trust agent reports')
CACHE_DIR_NAMES = {'__pycache__', '.pytest_cache', '.mypy_cache'}
GENERATED_FILE_PATTERNS = ('*.zip', '*.pyc', '*.pyo')
ALWAYS_SKIP_DIR_NAMES = {'.git', 'dist', '.fixture-tmp', '.fixture-work'}
SYNC_SKIP_NAMES = EXCLUDED_NAMES | {'.claude-plugin'}
def as_repo_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()
def normalize_relative(path: Path, repo_root: Path) -> Path:
    return path.resolve().relative_to(repo_root.resolve())
def iter_visible_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in ALWAYS_SKIP_DIR_NAMES]
        current_path = Path(current)
        for filename in filenames:
            files.append(current_path / filename)
    return files
def iter_visible_dirs(root: Path) -> list[Path]:
    dirs: list[Path] = []
    for current, dirnames, _filenames in os.walk(root):
        visible = [name for name in dirnames if name not in ALWAYS_SKIP_DIR_NAMES]
        dirnames[:] = visible
        current_path = Path(current)
        dirs.extend((current_path / name for name in visible))
    return dirs

def visible_paths(root: Path, pattern: str) -> list[Path]:
    return [path for path in iter_visible_files(root) if fnmatch.fnmatch(path.name, pattern)]

def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()

def tree_fingerprint(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SYNC_SKIP_NAMES and name not in ALWAYS_SKIP_DIR_NAMES]
        current_path = Path(current)
        for filename in filenames:
            path = current_path / filename
            relative = path.relative_to(root)
            if any((part in EXCLUDED_NAMES for part in relative.parts)):
                continue
            files[relative.as_posix()] = file_digest(path)
    return files

def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8-sig').replace('\r\n', '\n')

def expect(errors: list[str], bad: bool, message: str) -> None:
    if bad:
        errors.append(message)

def check_expected_set(actual: set[Path], expected: set[Path], label: str, ok_detail: str, reporter: 'Reporter') -> None:
    extra = sorted(actual - expected)
    missing = sorted(expected - actual)
    if not extra and (not missing):
        reporter.pass_check(label, ok_detail)
        return
    details = []
    if extra:
        details.append('extra: ' + ', '.join((path.as_posix() for path in extra)))
    if missing:
        details.append('missing: ' + ', '.join((path.as_posix() for path in missing)))
    reporter.fail_check(label, '; '.join(details))

class Reporter:

    def __init__(self) -> None:
        self.checks: list[dict[str, str]] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def pass_check(self, name: str, detail: str) -> None:
        self.checks.append({'name': name, 'status': 'pass', 'detail': detail})

    def fail_check(self, name: str, detail: str) -> None:
        self.checks.append({'name': name, 'status': 'fail', 'detail': detail})
        self.errors.append(f'{name}: {detail}')

def check_expected_paths(repo_root: Path, reporter: Reporter) -> None:
    for label, relative in PACKAGE_DIRS.items():
        path = repo_root / relative
        if path.is_dir():
            reporter.pass_check(label, f'found {relative.as_posix()}')
        else:
            reporter.fail_check(label, f'missing directory {relative.as_posix()}')
    for relative in EXPECTED_AGENT_FILES | EXPECTED_CHATBOT_FILES | EXPECTED_COMMAND_FILES | EXPECTED_CONTEXT_FILES | EXPECTED_CURSOR_RULE_FILES | EXPECTED_INSTALL_FILES | EXPECTED_PLUGIN_FILES | EXPECTED_PROMPTS | EXPECTED_SKILL_FILES:
        path = repo_root / relative
        if path.is_file():
            reporter.pass_check('expected file', f'found {relative.as_posix()}')
        else:
            reporter.fail_check('expected file', f'missing {relative.as_posix()}')

def check_instance_counts(repo_root: Path, reporter: Reporter) -> None:
    skill_files = {normalize_relative(path, repo_root) for path in visible_paths(repo_root, 'SKILL.md')}
    check_expected_set(skill_files, EXPECTED_SKILL_FILES, 'skill instance count', 'found trainer, clean, skeleton, Codex plugin, Claude AI, Cursor, and Antigravity skills', reporter)
    command_files = {normalize_relative(path, repo_root) for path in visible_paths(repo_root, '*.md') if '/.claude/commands/' in path.as_posix()}
    check_expected_set(command_files, EXPECTED_COMMAND_FILES, 'Claude command count', 'found exactly one Claude command', reporter)
    cursor_rule_files = {normalize_relative(path, repo_root) for path in (repo_root / '.cursor' / 'rules').glob('*.mdc') if path.is_file()}
    check_expected_set(cursor_rule_files, EXPECTED_CURSOR_RULE_FILES, 'Cursor rule count', 'found exactly one Cursor rule', reporter)
    prompt_files = {normalize_relative(path, repo_root) for path in (repo_root / 'portable-prompts').glob('*.md') if path.is_file()}
    check_expected_set(prompt_files, EXPECTED_PROMPTS, 'chat prompt count', 'found exactly one portable chat prompt', reporter)

def check_native_ai_entrypoints(repo_root: Path, reporter: Reporter) -> None:
    clean_skill_path = repo_root / 'code-hygiene' / 'SKILL.md'
    if clean_skill_path.is_file():
        clean_skill = read_text(clean_skill_path)
        for relative in EXPECTED_NATIVE_AI_SKILL_FILES:
            path = repo_root / relative
            if not path.is_file():
                continue
            if read_text(path) != clean_skill:
                reporter.fail_check('native AI skill sync', f'{relative.as_posix()} must match code-hygiene/SKILL.md')
            else:
                reporter.pass_check('native AI skill sync', f'{relative.as_posix()} matches code-hygiene/SKILL.md')
    for relative in EXPECTED_CURSOR_RULE_FILES:
        path = repo_root / relative
        if not path.is_file():
            continue
        text = read_text(path)
        missing = [
            snippet
            for snippet in ('smallest deterministic feedback loop', '.cursor/skills/code-hygiene/SKILL.md')
            if snippet not in text
        ]
        if missing:
            reporter.fail_check('Cursor rule content', f"{relative.as_posix()} missing required text: {', '.join(missing)}")
        else:
            reporter.pass_check('Cursor rule content', f'{relative.as_posix()} includes workflow and skill link')

def check_portable_prompt_content(repo_root: Path, reporter: Reporter) -> None:
    for relative in EXPECTED_PROMPTS:
        path = repo_root / relative
        if not path.is_file():
            continue
        text = read_text(path)
        expected = build_portable_prompt(repo_root / PACKAGE_DIRS['codex_skill']).replace('\r\n', '\n')
        if text != expected:
            reporter.fail_check('portable prompt sync', f'{relative.as_posix()} is stale; regenerate with export_claude_package.py --format portable-prompt')
        else:
            reporter.pass_check('portable prompt sync', f'{relative.as_posix()} matches generated prompt')

def check_entrypoint_content(repo_root: Path, reporter: Reporter) -> None:
    for relative in EXPECTED_AGENT_FILES:
        path = repo_root / relative
        if not path.is_file():
            continue
        text = read_text(path)
        missing = [snippet for snippet in OPENAI_AGENT_REQUIRED_SNIPPETS if snippet not in text]
        if missing:
            reporter.fail_check('OpenAI agent entrypoint', f"{relative.as_posix()} missing required text: {', '.join(missing)}")
        else:
            reporter.pass_check('OpenAI agent entrypoint', f'{relative.as_posix()} includes required summary')
    missing_command = [snippet for snippet in COMMAND_REQUIRED_SNIPPETS if snippet not in COMMAND_TEXT]
    if missing_command:
        reporter.fail_check('Claude command template', 'COMMAND_TEXT missing required text: ' + ', '.join(missing_command))
    else:
        reporter.pass_check('Claude command template', 'COMMAND_TEXT includes feedback-loop and evidence rules')
    for relative in EXPECTED_INSTALL_FILES:
        path = repo_root / relative
        if not path.is_file():
            continue
        text = read_text(path)
        if 'Exported at' in text:
            reporter.fail_check('install text', f'{relative.as_posix()} contains non-deterministic export timestamp')
        else:
            reporter.pass_check('install text', f'{relative.as_posix()} is deterministic')

def load_json(path: Path, repo_root: Path, label: str, reporter: Reporter) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        reporter.fail_check(label, f'invalid JSON in {as_repo_path(path, repo_root)}: {exc}')
        return None
    if not isinstance(payload, dict):
        reporter.fail_check(label, f'{path.name} must contain a JSON object')
        return None
    return payload

def check_claude_plugin_marketplace(repo_root: Path, reporter: Reporter) -> None:
    marketplace_path = repo_root / '.claude-plugin' / 'marketplace.json'
    manifest_path = repo_root / PACKAGE_DIRS['codex_skill'] / '.claude-plugin' / 'plugin.json'
    if not marketplace_path.is_file() or not manifest_path.is_file():
        return
    marketplace = load_json(marketplace_path, repo_root, 'Claude marketplace', reporter)
    manifest = load_json(manifest_path, repo_root, 'Claude plugin manifest', reporter)
    if marketplace is None or manifest is None:
        return
    plugins = marketplace.get('plugins')
    matching = [item for item in plugins or [] if isinstance(item, dict) and item.get('name') == PLUGIN_NAME]
    errors: list[str] = []
    owner = marketplace.get('owner')
    expect(errors, marketplace.get('name') != MARKETPLACE_NAME, f'marketplace name must be {MARKETPLACE_NAME}')
    expect(errors, not isinstance(owner, dict) or not owner.get('name'), 'marketplace owner.name is required')
    expect(errors, not isinstance(plugins, list) or len(matching) != 1, f'marketplace must contain exactly one {PLUGIN_NAME} plugin entry')
    if matching:
        expect(errors, matching[0].get('source') != PLUGIN_SOURCE, f'{PLUGIN_NAME} source must be {PLUGIN_SOURCE}')
    expect(errors, any((isinstance(item, dict) and 'version' in item for item in matching)), 'marketplace plugin entry must omit version for commit-SHA updates')
    for key, value in {'name': PLUGIN_NAME, 'repository': PLUGIN_REPOSITORY, 'skills': ['./'], 'agents': []}.items():
        expect(errors, manifest.get(key) != value, f'plugin manifest {key} must be {value}')
    expect(errors, 'version' in manifest, 'plugin manifest must omit version for commit-SHA updates')
    if errors:
        reporter.fail_check('Claude plugin marketplace', '; '.join(errors))
    else:
        reporter.pass_check('Claude plugin marketplace', 'marketplace and plugin manifest use commit-SHA versioning')

def check_codex_plugin_marketplace(repo_root: Path, reporter: Reporter) -> None:
    marketplace_path = repo_root / '.agents' / 'plugins' / 'marketplace.json'
    manifest_path = repo_root / 'plugins' / PLUGIN_NAME / '.codex-plugin' / 'plugin.json'
    if not marketplace_path.is_file() or not manifest_path.is_file():
        return
    marketplace = load_json(marketplace_path, repo_root, 'Codex marketplace', reporter)
    manifest = load_json(manifest_path, repo_root, 'Codex plugin manifest', reporter)
    if marketplace is None or manifest is None:
        return
    plugins = marketplace.get('plugins')
    matching = [item for item in plugins or [] if isinstance(item, dict) and item.get('name') == PLUGIN_NAME]
    errors: list[str] = []
    expect(errors, marketplace.get('name') != MARKETPLACE_NAME, f'marketplace name must be {MARKETPLACE_NAME}')
    expect(errors, not isinstance(marketplace.get('interface'), dict) or not marketplace['interface'].get('displayName'), 'marketplace interface.displayName is required')
    expect(errors, not isinstance(plugins, list) or len(matching) != 1, f'marketplace must contain exactly one {PLUGIN_NAME} plugin entry')
    if matching:
        entry = matching[0]
        for key, value in {'source': {'source': 'local', 'path': CODEX_PLUGIN_SOURCE}, 'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Coding'}.items():
            expect(errors, entry.get(key) != value, f'marketplace {key} is invalid')
    interface = manifest.get('interface')
    for key, value in {'name': PLUGIN_NAME, 'version': CODEX_PLUGIN_VERSION, 'repository': PLUGIN_REPOSITORY, 'skills': './skills/'}.items():
        expect(errors, manifest.get(key) != value, f'plugin manifest {key} is invalid')
    expect(errors, not isinstance(interface, dict) or interface.get('displayName') != 'Code Hygiene Compounder', 'plugin manifest interface.displayName is required')
    expect(errors, '[TODO:' in json.dumps({'marketplace': marketplace, 'manifest': manifest}, sort_keys=True), 'Codex marketplace files must not contain TODO placeholders')
    if errors:
        reporter.fail_check('Codex plugin marketplace', '; '.join(errors))
    else:
        reporter.pass_check('Codex plugin marketplace', 'marketplace and plugin manifest are public-ready')

def check_generated_artifacts(repo_root: Path, allow_runs: bool, reporter: Reporter) -> None:
    bad_files = []
    for pattern in GENERATED_FILE_PATTERNS:
        bad_files.extend(visible_paths(repo_root, pattern))
    if bad_files:
        detail = ', '.join((as_repo_path(path, repo_root) for path in sorted(bad_files)))
        reporter.fail_check('generated files', f'remove generated artifacts: {detail}')
    else:
        reporter.pass_check('generated files', 'no zip or bytecode artifacts found')
    bad_dir_names = set(CACHE_DIR_NAMES)
    if not allow_runs:
        bad_dir_names.add('runs')
    bad_dirs = [path for path in iter_visible_dirs(repo_root) if path.name in bad_dir_names]
    if bad_dirs:
        detail = ', '.join((as_repo_path(path, repo_root) for path in sorted(bad_dirs)))
        reporter.fail_check('generated directories', f'remove generated directories: {detail}')
    else:
        reporter.pass_check('generated directories', 'no cache or run directories found')

def check_source_packs(codex_root: Path, reporter: Reporter) -> None:
    weights_path = codex_root / 'references' / 'source-weights.json'
    packs_dir = codex_root / 'references' / 'source-packs'
    if not weights_path.is_file() or not packs_dir.is_dir():
        reporter.fail_check('source corpus', 'missing source weights or source-packs directory')
        return
    try:
        weights_payload = json.loads(weights_path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        reporter.fail_check('source weights', f'invalid JSON: {exc}')
        return
    weights = weights_payload.get('weights')
    if not isinstance(weights, list) or not weights:
        reporter.fail_check('source weights', 'weights must be a non-empty array')
        return
    ids: list[str] = []
    weight_errors: list[str] = []
    for index, item in enumerate(weights):
        if not isinstance(item, dict):
            weight_errors.append(f'weights[{index}] must be an object')
        elif not isinstance(item.get('id'), str) or not item['id'].strip():
            weight_errors.append(f'weights[{index}].id must be a non-empty string')
        else:
            ids.append(item['id'])
    if weight_errors:
        reporter.fail_check('source weights', '; '.join(weight_errors[:5]))
        return
    duplicate_ids = sorted({source_id for source_id in ids if ids.count(source_id) > 1})
    weight_ids = set(ids)
    pack_ids = {path.stem for path in packs_dir.glob('*.md')}
    missing_packs = sorted(weight_ids - pack_ids)
    extra_packs = sorted(pack_ids - weight_ids)
    if duplicate_ids or missing_packs or extra_packs:
        details = []
        if duplicate_ids:
            details.append('duplicate weight ids: ' + ', '.join(duplicate_ids))
        if missing_packs:
            details.append('missing packs: ' + ', '.join(missing_packs))
        if extra_packs:
            details.append('extra packs: ' + ', '.join(extra_packs))
        reporter.fail_check('source pack coverage', '; '.join(details))
    else:
        reporter.pass_check('source pack coverage', f'{len(weight_ids)} weighted sources have packs')
    malformed = []
    for path in packs_dir.glob('*.md'):
        text = read_text(path)
        if '## Distilled Checks' not in text or '## PASS-100 Focus' not in text:
            malformed.append(path.name)
    if malformed:
        reporter.fail_check('source pack shape', 'missing expected sections: ' + ', '.join(sorted(malformed)))
    else:
        reporter.pass_check('source pack shape', 'all source packs include checks and PASS-100 focus')

def check_context_index(codex_root: Path, reporter: Reporter) -> None:
    index_path = codex_root / 'references' / 'context-index.json'
    schema_path = codex_root / 'references' / 'context-index.schema.json'
    if not index_path.is_file():
        reporter.fail_check('context index', 'missing references/context-index.json')
        return
    if not schema_path.is_file():
        reporter.fail_check('context index', 'missing references/context-index.schema.json')
        return
    existing = load_json(index_path, codex_root, 'context index', reporter)
    if existing is None or load_json(schema_path, codex_root, 'context index schema', reporter) is None:
        return
    errors = context_index_errors(codex_root, existing)
    detail = '; '.join(errors[:8]) if errors else f'{len(existing.get("files", []))} indexed files are current'
    (reporter.fail_check if errors else reporter.pass_check)('context index', detail)

def check_tree_sync(source: Path, target: Path, label: str, reporter: Reporter) -> None:
    if not source.is_dir() or not target.is_dir():
        reporter.fail_check(label, 'source or target directory is missing')
        return
    source_files = tree_fingerprint(source)
    target_files = tree_fingerprint(target)
    missing = sorted(set(source_files) - set(target_files))
    extra = sorted(set(target_files) - set(source_files))
    changed = sorted((path for path in set(source_files) & set(target_files) if source_files[path] != target_files[path]))
    if missing or extra or changed:
        details = []
        if missing:
            details.append('missing: ' + ', '.join(missing))
        if extra:
            details.append('extra: ' + ', '.join(extra))
        if changed:
            details.append('changed: ' + ', '.join(changed))
        reporter.fail_check(label, '; '.join(details))
    else:
        reporter.pass_check(label, f'{len(source_files)} files match')

def check_export_sync(repo_root: Path, reporter: Reporter) -> None:
    codex_root = repo_root / PACKAGE_DIRS['codex_skill']
    codex_plugin_root = repo_root / PACKAGE_DIRS['codex_plugin_skill']
    claude_ai_root = repo_root / PACKAGE_DIRS['claude_ai_skill']
    command_root = repo_root / PACKAGE_DIRS['claude_command_package']
    if (claude_ai_root / 'SKILL.md').is_file():
        expected = read_skill_text(codex_root).replace('\r\n', '\n')
        actual = read_text(claude_ai_root / 'SKILL.md')
        if actual == expected:
            reporter.pass_check('Claude AI SKILL.md sync', 'frontmatter-normalized skill export matches')
        else:
            reporter.fail_check('Claude AI SKILL.md sync', 'Claude AI skill is stale')
    command_path = repo_root / 'code-hygiene-compounder-command' / '.claude' / 'commands' / 'code-hygiene.md'
    if command_path.is_file():
        actual = read_text(command_path).strip()
        expected = COMMAND_TEXT.replace('\r\n', '\n').strip()
        if actual == expected:
            reporter.pass_check('Claude command sync', 'command text matches export template')
        else:
            reporter.fail_check('Claude command sync', 'Claude command text is stale')
    check_tree_sync(codex_root, codex_plugin_root, 'Codex plugin skill sync', reporter)
    for relative in ('references', 'scripts', 'fixtures'):
        source = codex_root / relative
        if not source.exists():
            continue
        check_tree_sync(source, claude_ai_root / relative, f'Claude AI {relative} sync', reporter)
        check_tree_sync(source, command_root / relative, f'Claude command {relative} sync', reporter)

def validate(repo_root: Path, allow_runs: bool) -> dict:
    reporter = Reporter()
    repo_root = repo_root.resolve()
    check_expected_paths(repo_root, reporter)
    check_instance_counts(repo_root, reporter)
    check_native_ai_entrypoints(repo_root, reporter)
    check_portable_prompt_content(repo_root, reporter)
    check_entrypoint_content(repo_root, reporter)
    check_claude_plugin_marketplace(repo_root, reporter)
    check_codex_plugin_marketplace(repo_root, reporter)
    check_generated_artifacts(repo_root, allow_runs, reporter)
    check_source_packs(repo_root / PACKAGE_DIRS['codex_skill'], reporter)
    check_context_index(repo_root / PACKAGE_DIRS['codex_skill'], reporter)
    check_export_sync(repo_root, reporter)
    return {'valid': not reporter.errors, 'repo_root': str(repo_root), 'checks': reporter.checks, 'errors': reporter.errors, 'warnings': reporter.warnings}

def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]

def main() -> None:
    parser = argparse.ArgumentParser(description='Validate the package workspace shape.')
    parser.add_argument('--repo-root', type=Path, default=default_repo_root())
    parser.add_argument('--allow-runs', action='store_true', help='Do not fail when runs/ directories exist.')
    parser.add_argument('--json', action='store_true', help='Print full JSON instead of a short summary.')
    args = parser.parse_args()
    result = validate(args.repo_root, args.allow_runs)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = 'valid' if result['valid'] else 'invalid'
        print(f'Package validation: {status}')
        for check in result['checks']:
            print(f"[{check['status']}] {check['name']}: {check['detail']}")
    if not result['valid']:
        raise SystemExit(1)
if __name__ == '__main__':
    main()
