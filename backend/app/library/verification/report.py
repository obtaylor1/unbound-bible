"""Deterministic serialization and atomic writing for verification reports."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import html
import json
import os
from pathlib import Path
import stat
import tempfile
import unicodedata

from app.library.verification.types import WorkComparisonReport


def _report_dict(report: WorkComparisonReport) -> dict[str, object]:
    if type(report) is not WorkComparisonReport:
        raise ValueError('report must be a WorkComparisonReport.')
    return {
        'schema_version': report.schema_version,
        'work_id': report.work_id,
        'source_artifact_sha256': report.source_artifact.sha256,
        'current_publication_sha256': report.current_publication.sha256,
        'parser_version': report.parser_version,
        'rules': {
            'unicode_form': report.rules.unicode_form,
            'normalize_line_endings': report.rules.normalize_line_endings,
            'collapse_whitespace': report.rules.collapse_whitespace,
        },
        'totals': {
            'exact': report.totals.exact,
            'formatting': report.totals.formatting,
            'missing': report.totals.missing,
            'extra': report.totals.extra,
            'wording': report.totals.wording,
        },
        'declared_omissions': [
            {'chapter': position.chapter, 'verse': position.verse}
            for position in report.declared_omissions
        ],
        'differences': [
            {
                'chapter': difference.position.chapter,
                'verse': difference.position.verse,
                'classification': difference.classification.value,
                'current_text': difference.current_text,
                'source_text': difference.source_text,
            }
            for difference in report.differences
        ],
        'is_verified_candidate': report.is_verified_candidate,
    }


def report_json_bytes(report: WorkComparisonReport) -> bytes:
    payload = json.dumps(
        _report_dict(report),
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    return (payload + '\n').encode('utf-8')


def report_sha256(report: WorkComparisonReport) -> str:
    return sha256(report_json_bytes(report)).hexdigest()


def _markdown_text_block(value: str | None) -> tuple[str, str, str]:
    serialized = json.dumps(value, ensure_ascii=False)
    escaped = html.escape(serialized, quote=False)
    longest_backtick_run = 0
    current_run = 0
    for character in escaped:
        if character == '`':
            current_run += 1
            longest_backtick_run = max(longest_backtick_run, current_run)
        else:
            current_run = 0
    fence = '`' * max(3, longest_backtick_run + 1)
    return f'{fence}text', escaped, fence


def report_markdown(report: WorkComparisonReport) -> str:
    _report_dict(report)
    omissions = ', '.join(
        f'{position.chapter}:{position.verse}' for position in report.declared_omissions
    ) or 'None'
    verified = str(report.is_verified_candidate).lower()
    lines = [
        '# Scripture Source Verification Report',
        '',
        '## Identity',
        '',
        f'- Schema version: {report.schema_version}',
        '- Work:',
        '',
        *_markdown_text_block(report.work_id),
        f'- Source artifact SHA-256: `{report.source_artifact.sha256}`',
        f'- Current publication SHA-256: `{report.current_publication.sha256}`',
        '- Parser version:',
        '',
        *_markdown_text_block(report.parser_version),
        f'- Verified candidate: `{verified}`',
        '',
        '## Rules',
        '',
        f'- Unicode form: `{report.rules.unicode_form}`',
        f'- Normalize line endings: `{str(report.rules.normalize_line_endings).lower()}`',
        f'- Collapse whitespace: `{str(report.rules.collapse_whitespace).lower()}`',
        '',
        '## Totals',
        '',
        f'- Exact: {report.totals.exact}',
        f'- Formatting: {report.totals.formatting}',
        f'- Missing: {report.totals.missing}',
        f'- Extra: {report.totals.extra}',
        f'- Wording: {report.totals.wording}',
        '',
        '## Declared omissions',
        '',
        omissions,
        '',
        '## Differences',
        '',
    ]
    if not report.differences:
        lines.append('None')
    for difference in report.differences:
        lines.extend([
            f'### {difference.position.chapter}:{difference.position.verse} '
            f'— {difference.classification.value}',
            '',
            'Current text:',
            '',
            *_markdown_text_block(difference.current_text),
            '',
            'Source text:',
            '',
            *_markdown_text_block(difference.source_text),
            '',
        ])
    return '\n'.join(lines).rstrip() + '\n'


@dataclass(frozen=True, slots=True)
class ReportWriteResult:
    json_path: Path
    markdown_path: Path
    json_sha256: str


class ReportPairWriteError(OSError):
    """A pair transaction failed and may require explicit file recovery."""

    def __init__(
        self,
        primary_error: BaseException,
        *,
        rollback_errors: tuple[BaseException, ...] = (),
        cleanup_errors: tuple[BaseException, ...] = (),
        recovery_paths: tuple[Path, ...] = (),
    ) -> None:
        self.primary_error = primary_error
        self.rollback_errors = rollback_errors
        self.cleanup_errors = cleanup_errors
        self.recovery_paths = tuple(dict.fromkeys(recovery_paths))
        details = [f'report pair transaction failed: {primary_error}']
        if rollback_errors:
            details.append(
                'rollback errors: ' + '; '.join(str(error) for error in rollback_errors)
            )
        if cleanup_errors:
            details.append(
                'cleanup errors: ' + '; '.join(str(error) for error in cleanup_errors)
            )
        if self.recovery_paths:
            details.append(
                'manual recovery required: inspect retained paths; restore .backup '
                'files to their corresponding report outputs or remove an incomplete '
                'new output: '
                + ', '.join(str(path) for path in self.recovery_paths)
            )
        super().__init__('; '.join(details))


@dataclass(slots=True)
class _ReportFileState:
    final_path: Path
    data: bytes
    had_original: bool
    staged_path: Path | None = None
    backup_path: Path | None = None
    original_moved: bool = False
    new_installed: bool = False
    restore_failed: bool = False


def _validate_stem(stem: object) -> str:
    if type(stem) is not str or not stem or stem != stem.strip():
        raise ValueError('stem must be a nonblank trimmed string.')
    if stem in {'.', '..'} or Path(stem).is_absolute() or '/' in stem or '\\' in stem:
        raise ValueError('stem must be a single safe path component.')
    if stem.endswith(('.json', '.md')):
        raise ValueError('stem must not include a report extension.')
    if any(unicodedata.category(character).startswith('C') for character in stem):
        raise ValueError('stem must not contain control characters.')
    return stem


def _write_temp_file(path: Path, data: bytes) -> Path:
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception as primary_error:
        try:
            _remove_file(temp_path, 'cleanup-temp-write')
        except Exception as cleanup_error:
            error = ReportPairWriteError(
                primary_error,
                cleanup_errors=(cleanup_error,),
                recovery_paths=(temp_path,),
            )
            raise error from primary_error
        raise
    return temp_path


def _reserve_backup_path(path: Path) -> Path:
    descriptor, backup_name = tempfile.mkstemp(
        prefix=f'.{path.name}.', suffix='.backup', dir=path.parent,
    )
    backup_path = Path(backup_name)
    try:
        os.close(descriptor)
    except Exception as primary_error:
        try:
            _remove_file(backup_path, 'cleanup-backup-reservation')
        except Exception as cleanup_error:
            error = ReportPairWriteError(
                primary_error,
                cleanup_errors=(cleanup_error,),
                recovery_paths=(backup_path,),
            )
            raise error from primary_error
        raise
    return backup_path


def _move_file(source: Path, destination: Path, operation: str) -> None:
    del operation
    os.replace(source, destination)


def _remove_file(path: Path, operation: str) -> None:
    del operation
    path.unlink(missing_ok=True)


def _lstat_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _inspect_existing_pair(final_paths: tuple[Path, Path]) -> bool:
    existing = []
    for path in final_paths:
        try:
            status = path.lstat()
        except FileNotFoundError:
            existing.append(False)
            continue
        if not stat.S_ISREG(status.st_mode):
            raise ValueError(f'pre-existing report output must be a regular file: {path}.')
        existing.append(True)
    if existing[0] != existing[1]:
        raise ValueError('pre-existing report outputs must be a complete pair.')
    return existing[0]


def _rollback_pair(
    states: tuple[_ReportFileState, _ReportFileState],
) -> tuple[list[BaseException], list[Path]]:
    errors: list[BaseException] = []
    recovery_paths: list[Path] = []
    for state in states:
        if not state.new_installed:
            continue
        try:
            _remove_file(state.final_path, 'rollback-new')
            state.new_installed = False
        except Exception as error:
            errors.append(error)
            if not state.had_original:
                recovery_paths.append(state.final_path)

    for state in states:
        if not state.original_moved or state.backup_path is None:
            continue
        try:
            _move_file(state.backup_path, state.final_path, 'restore')
            state.original_moved = False
        except Exception as error:
            state.restore_failed = True
            errors.append(error)
            recovery_paths.append(state.backup_path)
    return errors, recovery_paths


def _cleanup_pair(
    states: tuple[_ReportFileState, _ReportFileState],
) -> tuple[list[BaseException], list[Path]]:
    errors: list[BaseException] = []
    recovery_paths: list[Path] = []
    candidates: list[tuple[Path, str]] = []
    for state in states:
        if state.staged_path is not None:
            candidates.append((state.staged_path, 'cleanup'))
        if state.backup_path is not None and not state.restore_failed:
            candidates.append((state.backup_path, 'cleanup-backup'))

    for path, operation in candidates:
        try:
            if _lstat_exists(path):
                _remove_file(path, operation)
        except Exception as error:
            errors.append(error)
            recovery_paths.append(path)
    return errors, recovery_paths


def _transaction_error(
    primary_error: BaseException,
    *,
    rollback_errors: list[BaseException],
    cleanup_errors: list[BaseException],
    recovery_paths: list[Path],
) -> ReportPairWriteError:
    if isinstance(primary_error, ReportPairWriteError):
        rollback_errors = list(primary_error.rollback_errors) + rollback_errors
        cleanup_errors = list(primary_error.cleanup_errors) + cleanup_errors
        recovery_paths = list(primary_error.recovery_paths) + recovery_paths
        primary_error = primary_error.primary_error
    return ReportPairWriteError(
        primary_error,
        rollback_errors=tuple(rollback_errors),
        cleanup_errors=tuple(cleanup_errors),
        recovery_paths=tuple(recovery_paths),
    )


def write_report_pair(
    report: WorkComparisonReport, output_dir: str | os.PathLike[str], stem: str,
) -> ReportWriteResult:
    safe_stem = _validate_stem(stem)
    json_data = report_json_bytes(report)
    markdown_data = report_markdown(report).encode('utf-8')
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f'{safe_stem}.json'
    markdown_path = directory / f'{safe_stem}.md'
    final_paths = (json_path, markdown_path)
    new_data = (json_data, markdown_data)
    had_original = _inspect_existing_pair(final_paths)
    states = tuple(
        _ReportFileState(final_path, data, had_original)
        for final_path, data in zip(final_paths, new_data, strict=True)
    )
    try:
        for state in states:
            state.staged_path = _write_temp_file(state.final_path, state.data)
        if had_original:
            for state in states:
                state.backup_path = _reserve_backup_path(state.final_path)
                _move_file(state.final_path, state.backup_path, 'backup')
                state.original_moved = True
        for state in states:
            assert state.staged_path is not None
            _move_file(state.staged_path, state.final_path, 'install')
            state.new_installed = True
    except Exception as primary_error:
        rollback_errors, rollback_recovery = _rollback_pair(states)
        cleanup_errors, cleanup_recovery = _cleanup_pair(states)
        error = _transaction_error(
            primary_error,
            rollback_errors=rollback_errors,
            cleanup_errors=cleanup_errors,
            recovery_paths=rollback_recovery + cleanup_recovery,
        )
        raise error from primary_error

    cleanup_errors, cleanup_recovery = _cleanup_pair(states)
    if cleanup_errors:
        error = ReportPairWriteError(
            cleanup_errors[0],
            cleanup_errors=tuple(cleanup_errors),
            recovery_paths=tuple(cleanup_recovery),
        )
        raise error from cleanup_errors[0]
    return ReportWriteResult(json_path, markdown_path, sha256(json_data).hexdigest())
