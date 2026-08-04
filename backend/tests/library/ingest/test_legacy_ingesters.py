import ast
import builtins
import http.client
import io
from pathlib import Path
import re
import runpy
import socket
import sqlite3
import ssl
import urllib.request

import pytest
import sqlalchemy
import sqlalchemy.orm


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
COMMON_WORKFLOW = (
    'run from the backend directory',
    'python -m app.library.ingest.cli stage --manifest <reviewed-manifest> --database-url <migrated-database-url>',
    'python -m app.library.ingest.cli validate --run-id <run-id> --database-url <migrated-database-url>',
    'python -m app.library.ingest.cli publish --run-id <run-id> --confirm --database-url <migrated-database-url>',
    'explicitly set database_url is permitted',
)
LEGACY_INGESTERS = {
    REPOSITORY_ROOT / 'add_popular_verse_translations.py': (
        'popular verse translation writer is retired',
        'reviewed manifest and installed adapter are unavailable',
    ),
    REPOSITORY_ROOT / 'backend/ingest_all_data.py': (
        'master direct ingestion launcher is retired',
        'does not run legacy ingestion scripts',
    ),
    REPOSITORY_ROOT / 'backend/ingest_kjv.py': (
        'direct kjv ingester is retired',
        'reviewed kjv manifest and installed adapter are unavailable',
    ),
    REPOSITORY_ROOT / 'backend/ingest_public_translations.py': (
        'direct public translation ingester is retired',
        'reviewed public translation manifests and installed adapters are unavailable',
    ),
    REPOSITORY_ROOT / 'backend/add_sample_translations.py': (
        'sample scripture writer is retired',
        'sample or placeholder scripture must not be published',
    ),
    REPOSITORY_ROOT / 'backend/data/ingest_adam_eve.py': (
        'direct adam and eve ingester is retired',
        'reviewed adam and eve manifest and installed adapter are unavailable',
    ),
    REPOSITORY_ROOT / 'backend/data/generate_embeddings_adameve.py': (
        'direct adam and eve embedding writer is retired',
        'published scripture rows are immutable outside the verified publisher',
    ),
    REPOSITORY_ROOT / 'server/data/ingest_core_originals.py': (
        'direct original-language ingester is retired',
        'reviewed original-language manifests and installed adapters are unavailable',
    ),
    REPOSITORY_ROOT / 'server/data/ingest_english_texts.py': (
        'direct english scripture ingester is retired',
        'reviewed english manifests and installed adapters are unavailable',
    ),
    REPOSITORY_ROOT / 'server/data/ingest_ethiopian_critical_texts.py': (
        'direct ethiopian critical-text ingester is retired',
        'reviewed ethiopian manifests and installed adapters are unavailable',
    ),
    REPOSITORY_ROOT / 'server/data/ingest_ertale_canon.py': (
        'legacy direct ertale ingester path is retired',
        'reviewed `ertale` adapter is planned for phase 3 and unavailable today',
        'stage --manifest <reviewed-manifest>',
        'validate --run-id <run-id>',
        'publish --run-id <run-id> --confirm',
    ),
    REPOSITORY_ROOT / 'server/data/ingest_ethiopian_canon.py': (
        'seed-canon',
        'python -m app.library.ingest.cli seed-canon --database-url <migrated-database-url>',
        'catalog only',
        'does not import verse text',
        'phase 3',
        'unavailable',
        'reviewed manifest and installed adapter',
        'once they are available',
        'stage --manifest <reviewed-manifest>',
        'validate --run-id <run-id>',
        'publish --run-id <run-id> --confirm',
    ),
    REPOSITORY_ROOT / 'server/data/ingest_report_data.py': (
        'mixed non-scripture auxiliary report data with unsafe ethiopian placeholders',
        'no matching scripture manifest or adapter is available',
        'unavailable',
        'separately reviewed migration',
        'ethiopian scripture uses the phase 3 safe cli',
        'stage --manifest <reviewed-manifest>',
        'validate --run-id <run-id>',
        'publish --run-id <run-id> --confirm',
    ),
}


_CODE_SUFFIXES = {'.py', '.sql', '.js', '.jsx', '.ts', '.tsx', '.sh'}
_SESSION_MUTATIONS = {
    'add', 'add_all', 'bulk_insert_mappings', 'bulk_save_objects', 'commit',
    'delete', 'execute', 'flush', 'merge', 'update',
}
_RAW_SCRIPTURE_WRITE = re.compile(
    r'(?is)\b(?:insert\s+into|delete\s+from|update)\s+["`\[]?biblical_texts["`\]]?\b'
)


def _constructs_biblical_text(tree: ast.AST) -> bool:
    constructor_names = {'BiblicalText'}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == 'BiblicalText':
                    constructor_names.add(alias.asname or alias.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if isinstance(value, ast.Attribute) and value.attr == 'BiblicalText':
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                constructor_names.update(
                    target.id for target in targets if isinstance(target, ast.Name)
                )

    return any(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name) and node.func.id in constructor_names
            or isinstance(node.func, ast.Attribute) and node.func.attr == 'BiblicalText'
        )
        for node in ast.walk(tree)
    )


def _mutates_session(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _SESSION_MUTATIONS
        for node in ast.walk(tree)
    )


def _approved_metadata_backfill(path: Path, source: str, match: re.Match[str]) -> bool:
    if path.name != 'migration_service.py' or not match.group(0).lstrip().lower().startswith('update'):
        return False
    statement = source[match.start():source.find(')', match.end()) + 1]
    normalized = ' '.join(statement.casefold().replace('"', '').split())
    return (
        'update biblical_texts set abstract_verse_id = :abstract_id' in normalized
        and ' text =' not in normalized
    )


def _find_scripture_write_violations(root: Path) -> list[str]:
    root = root.resolve()
    allowed_writer = (
        root / 'backend/app/library/ingest/publish.py'
        if (root / 'backend').is_dir()
        else None
    )
    violations: list[str] = []
    for path in sorted(candidate for candidate in root.rglob('*') if candidate.is_file()):
        relative = path.relative_to(root)
        if (
            path == allowed_writer
            or path.suffix.lower() not in _CODE_SUFFIXES
            or any(part in {
                '.git', '.worktrees', 'alembic', 'node_modules', 'tests', 'venv',
            } for part in relative.parts)
        ):
            continue
        try:
            source = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            violations.append(f'{relative}: non-UTF-8 executable source was not inspected')
            continue

        if path.suffix.lower() == '.py':
            tree = ast.parse(source)
            if _constructs_biblical_text(tree) and _mutates_session(tree):
                violations.append(f'{relative}: ORM scripture write')

        for match in _RAW_SCRIPTURE_WRITE.finditer(source):
            if not _approved_metadata_backfill(path, source, match):
                violations.append(f'{relative}: raw SQL scripture write')
    return violations


def test_writer_guard_detects_attribute_alias_and_split_helper_writes(tmp_path):
    candidate = tmp_path / 'writer.py'
    candidate.write_text(
        '''
import models

def make_row():
    return models.BiblicalText(book='Genesis', chapter=1, verse=1, text='unsafe')

def save(session, row):
    session.merge(row)
    session.flush()
''',
        encoding='utf-8',
    )

    assert _find_scripture_write_violations(tmp_path)


def test_writer_guard_detects_raw_writes_in_non_python_files(tmp_path):
    (tmp_path / 'writer.sql').write_text(
        'UPDATE "biblical_texts" SET text = \'unsafe\' WHERE id = 1;',
        encoding='utf-8',
    )

    assert _find_scripture_write_violations(tmp_path)


def test_only_verified_publisher_writes_scripture_rows():
    assert _find_scripture_write_violations(REPOSITORY_ROOT) == []


def _assert_inert_notice_structure(source, required_notice):
    tree = ast.parse(source)

    assert [type(node) for node in tree.body] == [
        ast.Expr, ast.Import, ast.Assign, ast.FunctionDef, ast.If,
    ]
    assert isinstance(tree.body[0].value, ast.Constant)
    assert isinstance(tree.body[0].value.value, str)
    assert [alias.name for alias in tree.body[1].names] == ['sys']
    assert all(alias.asname is None for alias in tree.body[1].names)

    notice = tree.body[2]
    assert len(notice.targets) == 1 and isinstance(notice.targets[0], ast.Name)
    assert notice.targets[0].id == 'NOTICE'
    assert isinstance(notice.value, ast.Constant)
    assert isinstance(notice.value.value, str)
    notice_text = notice.value.value.casefold()
    assert all(
        text.casefold() in notice_text for text in (*COMMON_WORKFLOW, *required_notice)
    )
    assert 'pythonpath=' not in notice_text

    main = tree.body[3]
    assert main.name == 'main'
    assert main.decorator_list == [] and main.returns is None
    assert not main.args.posonlyargs and not main.args.args and not main.args.kwonlyargs
    assert not main.args.defaults and not main.args.kw_defaults
    assert main.args.vararg is None and main.args.kwarg is None
    assert [type(node) for node in main.body] == [ast.Expr, ast.Return]
    print_call = main.body[0].value
    assert isinstance(print_call, ast.Call)
    assert isinstance(print_call.func, ast.Name) and print_call.func.id == 'print'
    assert len(print_call.args) == 1
    assert isinstance(print_call.args[0], ast.Name) and print_call.args[0].id == 'NOTICE'
    assert len(print_call.keywords) == 1 and print_call.keywords[0].arg == 'file'
    stream = print_call.keywords[0].value
    assert isinstance(stream, ast.Attribute) and stream.attr == 'stderr'
    assert isinstance(stream.value, ast.Name) and stream.value.id == 'sys'
    assert isinstance(main.body[1].value, ast.Constant) and main.body[1].value.value == 1

    guard = tree.body[4]
    assert guard.orelse == [] and isinstance(guard.test, ast.Compare)
    assert isinstance(guard.test.left, ast.Name) and guard.test.left.id == '__name__'
    assert len(guard.test.ops) == 1 and isinstance(guard.test.ops[0], ast.Eq)
    assert len(guard.test.comparators) == 1
    assert isinstance(guard.test.comparators[0], ast.Constant)
    assert guard.test.comparators[0].value == '__main__'
    assert len(guard.body) == 1 and isinstance(guard.body[0], ast.Raise)
    raised = guard.body[0].exc
    assert isinstance(raised, ast.Call)
    assert isinstance(raised.func, ast.Name) and raised.func.id == 'SystemExit'
    assert not raised.keywords and len(raised.args) == 1
    invoked_main = raised.args[0]
    assert isinstance(invoked_main, ast.Call)
    assert isinstance(invoked_main.func, ast.Name) and invoked_main.func.id == 'main'
    assert not invoked_main.args and not invoked_main.keywords


def _install_runtime_guards(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError('legacy ingester attempted a forbidden side effect')

    original_open = builtins.open
    original_io_open = io.open

    def read_only_open(file, mode='r', *args, **kwargs):
        if any(marker in mode for marker in ('w', 'a', 'x', '+')):
            forbidden(file, mode)
        return original_open(file, mode, *args, **kwargs)

    def read_only_io_open(file, mode='r', *args, **kwargs):
        if any(marker in mode for marker in ('w', 'a', 'x', '+')):
            forbidden(file, mode)
        return original_io_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', read_only_open)
    monkeypatch.setattr(io, 'open', read_only_io_open)
    monkeypatch.setattr(Path, 'write_text', forbidden)
    monkeypatch.setattr(Path, 'write_bytes', forbidden)
    monkeypatch.setattr(Path, 'touch', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(ssl, '_create_unverified_context', forbidden)
    monkeypatch.setattr(ssl, '_create_default_https_context', forbidden)
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(http.client, 'HTTPConnection', forbidden)
    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    monkeypatch.setattr(sqlalchemy, 'create_engine', forbidden)
    monkeypatch.setattr(sqlalchemy.orm, 'sessionmaker', forbidden)


@pytest.mark.parametrize('script,required_notice', LEGACY_INGESTERS.items())
def test_legacy_ingester_is_exact_inert_notice_program(script, required_notice):
    _assert_inert_notice_structure(script.read_text(encoding='utf-8'), required_notice)


def test_exact_structure_rejects_an_extra_main_print_expression():
    script, required_notice = next(iter(LEGACY_INGESTERS.items()))
    malicious = script.read_text(encoding='utf-8').replace(
        '    return 1', "    print('extra')\n    return 1",
    )

    with pytest.raises(AssertionError):
        _assert_inert_notice_structure(malicious, required_notice)


def test_exact_structure_rejects_inaccurate_ertale_guidance():
    script = REPOSITORY_ROOT / 'server/data/ingest_ertale_canon.py'
    required_notice = LEGACY_INGESTERS[script]
    inaccurate = script.read_text(encoding='utf-8').replace(
        'reviewed `ertale` adapter is planned for Phase 3 and unavailable today',
        'reviewed `ertale` adapter is ready today',
    )

    with pytest.raises(AssertionError):
        _assert_inert_notice_structure(inaccurate, required_notice)


@pytest.mark.parametrize('script', LEGACY_INGESTERS)
def test_legacy_ingester_import_is_silent_and_side_effect_free(script, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('HOME', str(tmp_path))
    before = set(tmp_path.rglob('*'))
    _install_runtime_guards(monkeypatch)

    namespace = runpy.run_path(str(script), run_name='legacy_ingester_import')

    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == ''
    assert namespace['main'].__name__ == 'main'
    assert set(tmp_path.rglob('*')) == before


@pytest.mark.parametrize('script', LEGACY_INGESTERS)
def test_legacy_ingester_main_is_nonzero_notice_under_runtime_safety_guards(
    script, tmp_path, monkeypatch, capsys
):
    _install_runtime_guards(monkeypatch)
    namespace = runpy.run_path(str(script), run_name='legacy_ingester_import')
    expected_notice = namespace['NOTICE'] + '\n'
    before = set(tmp_path.rglob('*'))

    assert namespace['main']() == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == expected_notice
    assert set(tmp_path.rglob('*')) == before
