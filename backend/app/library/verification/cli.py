"""Local-only source locking and adapter orchestration commands.

No command in this module downloads an artifact.  Family parsers and candidate
builders are deliberately absent until separately reviewed adapters are installed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Annotated, NoReturn, Protocol

import typer

# Keep result-type identity stable when this operator CLI is launched with
# ``python -m`` and adapters import its public result types by package name.
if __name__ == '__main__':
    sys.modules['app.library.verification.cli'] = sys.modules[__name__]

from app.library.verification.adapters.wmb_vpl import WmbVplAdapter
from app.library.verification.adapters.murdock_sword import MurdockSwordAdapter
from app.library.verification.adapters.gutenberg_kjv_apocrypha import (
    GutenbergKjvApocryphaAdapter,
)
from app.library.verification.adapters.charles_jubilees import CharlesJubileesAdapter
from app.library.verification.registry import (
    ArtifactLock,
    ArtifactLockRecord,
    SourceDefinition,
    _load_json,
    compute_artifact_identity,
    load_artifact_lock,
    load_source_registry,
    validate_https_url,
    verify_artifact,
    write_artifact_lock,
)
from app.library.verification.types import (
    ComparisonCounts,
    ComparisonRules,
    CurrentPublicationIdentity,
    DifferenceClassification,
    SourceArtifactIdentity,
    VerseDifference,
    VersePosition,
    WorkComparisonReport,
)


DEFAULT_VERIFICATION_DIR = (
    Path(__file__).parents[3] / 'data/scripture/eotc-composite-en/verification'
)
DEFAULT_REGISTRY = DEFAULT_VERIFICATION_DIR / 'source-registry.json'
DEFAULT_LOCK = DEFAULT_VERIFICATION_DIR / 'source-artifacts.lock.json'
DEFAULT_ARTIFACT_ROOT = DEFAULT_VERIFICATION_DIR / 'artifacts'


_OUTPUT_ID = re.compile(r'[a-z0-9][a-z0-9._-]{0,127}\Z')


def _safe_output_id(value: object) -> str:
    if type(value) is not str or _OUTPUT_ID.fullmatch(value) is None:
        raise ValueError('adapter output_id must be a bounded safe identifier.')
    return value


@dataclass(frozen=True, slots=True)
class CompareFamilyResult:
    report_count: int
    output_id: str

    def __post_init__(self) -> None:
        if type(self.report_count) is not int or not 0 <= self.report_count <= 100:
            raise ValueError('report_count must be a bounded nonnegative integer.')
        object.__setattr__(self, 'output_id', _safe_output_id(self.output_id))


@dataclass(frozen=True, slots=True)
class CandidateBuildResult:
    work_count: int
    output_id: str

    def __post_init__(self) -> None:
        if type(self.work_count) is not int or not 0 <= self.work_count <= 100:
            raise ValueError('work_count must be a bounded nonnegative integer.')
        object.__setattr__(self, 'output_id', _safe_output_id(self.output_id))


class VerificationAdapter(Protocol):
    """Explicit injection point for a later reviewed family adapter."""

    def compare_family(
        self,
        *,
        definition: SourceDefinition,
        lock_record: ArtifactLockRecord,
        artifact_path: Path,
        current_bundle: Path,
        output: Path,
    ) -> CompareFamilyResult: ...

    def build_candidate(
        self,
        *,
        definition: SourceDefinition,
        lock_record: ArtifactLockRecord,
        artifact_path: Path,
        report_dir: Path,
        output: Path,
        replace_from_source: bool,
    ) -> CandidateBuildResult: ...


# Only separately reviewed source-family adapters are installed here.
ADAPTERS: dict[str, VerificationAdapter] = {
    "wmb_vpl": WmbVplAdapter(),
    "murdock_sword": MurdockSwordAdapter(),
    "gutenberg_kjv_apocrypha": GutenbergKjvApocryphaAdapter(),
    "charles_jubilees": CharlesJubileesAdapter(),
}

app = typer.Typer(
    no_args_is_help=True,
    help='Lock reviewed local source artifacts and invoke explicitly installed adapters.',
)


def _emit(payload: Mapping[str, object]) -> None:
    typer.echo(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ))


def _fail(_error: Exception) -> NoReturn:
    _emit({
        'status': 'error',
        'code': 'operation_failed',
        'error': 'operation failed; review the supplied local inputs',
    })
    raise typer.Exit(code=1)


def _definition_and_lock(
    family_id: str,
    registry_path: Path,
    lock_path: Path,
) -> tuple[SourceDefinition, ArtifactLockRecord]:
    registry = load_source_registry(registry_path)
    definition = registry.families.get(family_id)
    if definition is None:
        raise ValueError('unknown source family.')
    lock = load_artifact_lock(lock_path)
    record = lock.artifacts.get(family_id)
    if record is None:
        raise ValueError(f'family {family_id} is not locked.')
    return definition, record


def lock_artifact_service(
    *,
    family_id: str,
    registry_path: Path,
    lock_path: Path,
    artifact_root: Path,
    file: Path,
    source_url: str,
    retrieved_at: object,
    replace: bool = False,
    confirm_family: str | None = None,
) -> ArtifactLockRecord:
    """Hash and lock a file already placed by an operator; never download it."""
    registry = load_source_registry(registry_path)
    definition = registry.families.get(family_id)
    if definition is None:
        raise ValueError('unknown source family.')
    root = artifact_root.resolve(strict=True)
    try:
        supplied = os.stat(file, follow_symlinks=False)
    except OSError as error:
        raise ValueError('artifact file is missing.') from error
    if stat.S_ISLNK(supplied.st_mode) or not stat.S_ISREG(supplied.st_mode):
        raise ValueError('artifact file must be a nonsymlink regular file.')
    resolved = file.resolve(strict=True)
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise ValueError('artifact file must be within the artifact root.') from error
    if relative.as_posix() != definition.artifact_filename:
        raise ValueError('artifact filename must exactly match the registry definition.')
    canonical_source = validate_https_url(
        source_url, allowed_hosts=definition.allowed_source_hosts,
    )
    if definition.artifact_url is not None and canonical_source != definition.artifact_url:
        raise ValueError('source URL must match the canonical registry artifact URL.')
    identity = compute_artifact_identity(resolved, definition.max_artifact_bytes)
    record = ArtifactLockRecord(
        family_id=family_id,
        artifact_path=relative.as_posix(),
        source_url=canonical_source,
        landing_url=definition.landing_url,
        retrieved_at=retrieved_at,
        size_bytes=identity.size_bytes,
        sha256=identity.sha256,
    )
    verify_artifact(record, definition, root)

    current = load_artifact_lock(lock_path)
    previous = current.artifacts.get(family_id)
    if previous is not None and previous != record:
        if not replace or confirm_family != family_id:
            raise ValueError(
                'a different lock already exists; use --replace and confirm with the exact family ID.'
            )
    if previous == record:
        return record
    updated = dict(current.artifacts)
    updated[family_id] = record
    write_artifact_lock(lock_path, ArtifactLock(version=1, artifacts=updated))
    return record


def compare_family_service(
    *,
    family_id: str,
    registry_path: Path,
    lock_path: Path,
    artifact_root: Path,
    current_bundle: Path,
    output: Path,
    adapters: Mapping[str, VerificationAdapter] | None = None,
) -> CompareFamilyResult:
    definition, record = _definition_and_lock(family_id, registry_path, lock_path)
    root = artifact_root.resolve(strict=True)
    verify_artifact(record, definition, root)
    installed = ADAPTERS if adapters is None else adapters
    adapter = installed.get(definition.adapter_id)
    if adapter is None:
        raise ValueError(f'adapter {definition.adapter_id} is not installed')
    try:
        result = adapter.compare_family(
            definition=definition,
            lock_record=record,
            artifact_path=root / record.artifact_path,
            current_bundle=current_bundle,
            output=output,
        )
    except Exception as error:
        raise ValueError(f'adapter {definition.adapter_id} failed') from error
    if type(result) is not CompareFamilyResult:
        raise ValueError('adapter returned an invalid compare result.')
    return result


_REPORT_FIELDS = {
    'schema_version', 'work_id', 'source_artifact_sha256',
    'current_publication_sha256', 'parser_version', 'rules', 'totals',
    'declared_omissions', 'differences', 'is_verified_candidate',
}


def _strict_object(value: object, fields: set[str], context: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise ValueError(f'{context} must contain exactly the required fields.')
    return value


def _strict_report(payload: object) -> WorkComparisonReport:
    report = _strict_object(payload, _REPORT_FIELDS, 'comparison report')
    if type(report['schema_version']) is not int or report['schema_version'] != 1:
        raise ValueError('comparison report must use schema version 1.')
    rules = _strict_object(
        report['rules'],
        {'unicode_form', 'normalize_line_endings', 'collapse_whitespace'},
        'comparison rules',
    )
    totals = _strict_object(
        report['totals'],
        {'exact', 'formatting', 'missing', 'extra', 'wording'},
        'comparison totals',
    )
    omissions_value = report['declared_omissions']
    differences_value = report['differences']
    if type(omissions_value) is not list or type(differences_value) is not list:
        raise ValueError('report omissions and differences must be lists.')
    omissions = tuple(
        VersePosition(**_strict_object(value, {'chapter', 'verse'}, 'declared omission'))
        for value in omissions_value
    )
    differences: list[VerseDifference] = []
    for value in differences_value:
        item = _strict_object(
            value,
            {'chapter', 'verse', 'classification', 'current_text', 'source_text'},
            'verse difference',
        )
        try:
            classification = DifferenceClassification(item['classification'])
        except (TypeError, ValueError) as error:
            raise ValueError('verse difference classification is invalid.') from error
        differences.append(VerseDifference(
            position=VersePosition(item['chapter'], item['verse']),
            classification=classification,
            current_text=item['current_text'],
            source_text=item['source_text'],
        ))
    parsed = WorkComparisonReport(
        schema_version=report['schema_version'],
        work_id=report['work_id'],
        source_artifact=SourceArtifactIdentity(report['source_artifact_sha256']),
        current_publication=CurrentPublicationIdentity(
            report['current_publication_sha256']
        ),
        parser_version=report['parser_version'],
        rules=ComparisonRules(**rules),
        totals=ComparisonCounts(**totals),
        declared_omissions=omissions,
        differences=tuple(differences),
    )
    if type(report['is_verified_candidate']) is not bool:
        raise ValueError('is_verified_candidate must be a boolean.')
    if report['is_verified_candidate'] != parsed.is_verified_candidate:
        raise ValueError('is_verified_candidate contradicts validated differences.')
    return parsed


def _unresolved_report_differences(
    report_dir: Path,
    definition: SourceDefinition,
    record: ArtifactLockRecord,
) -> int:
    if not report_dir.is_dir():
        raise ValueError('report directory is missing.')
    reports = sorted(report_dir.glob('*.json'))
    if not reports:
        raise ValueError('report directory contains no JSON comparison reports.')
    unresolved = 0
    seen_work_ids: set[str] = set()
    expected_work_ids = set(definition.expected_work_ids)
    for path in reports:
        report = _strict_report(_load_json(path))
        work_id = report.work_id
        if work_id not in expected_work_ids:
            raise ValueError(f'report {path.name} is not for an expected family work.')
        if work_id in seen_work_ids:
            raise ValueError(f'report set contains duplicate work_id {work_id}.')
        seen_work_ids.add(work_id)
        if report.source_artifact.sha256 != record.sha256:
            raise ValueError(f'report {path.name} is not bound to the locked artifact.')
        unresolved += sum(
            difference.classification in {
                DifferenceClassification.MISSING,
                DifferenceClassification.EXTRA,
                DifferenceClassification.WORDING,
            }
            for difference in report.differences
        )
    if seen_work_ids != expected_work_ids:
        raise ValueError('report set must be complete for the source family.')
    return unresolved


def build_candidate_service(
    *,
    family_id: str,
    registry_path: Path,
    lock_path: Path,
    artifact_root: Path,
    report_dir: Path,
    output: Path,
    replace_from_source: bool = False,
    adapters: Mapping[str, VerificationAdapter] | None = None,
) -> CandidateBuildResult:
    definition, record = _definition_and_lock(family_id, registry_path, lock_path)
    root = artifact_root.resolve(strict=True)
    verify_artifact(record, definition, root)
    installed = ADAPTERS if adapters is None else adapters
    adapter = installed.get(definition.adapter_id)
    if adapter is None:
        raise ValueError(f'adapter {definition.adapter_id} is not installed')
    unresolved = _unresolved_report_differences(report_dir, definition, record)
    if unresolved and not replace_from_source:
        raise ValueError(
            'comparison reports contain unresolved missing, extra, or wording differences; '
            'use --replace-from-source to build a source-derived candidate.'
        )
    try:
        result = adapter.build_candidate(
            definition=definition,
            lock_record=record,
            artifact_path=root / record.artifact_path,
            report_dir=report_dir,
            output=output,
            replace_from_source=replace_from_source,
        )
    except Exception as error:
        raise ValueError(f'adapter {definition.adapter_id} failed') from error
    if type(result) is not CandidateBuildResult:
        raise ValueError('adapter returned an invalid candidate result.')
    return result


@app.command('lock-artifact')
def lock_artifact_command(
    family: Annotated[str, typer.Argument(help='Exact reviewed source-family ID.')],
    file: Annotated[Path, typer.Option('--file', help='Existing local artifact file.')],
    source_url: Annotated[str, typer.Option('--source-url', help='Reviewed HTTPS source URL.')],
    retrieved_at: Annotated[str, typer.Option('--retrieved-at', help='Aware UTC ISO-8601 time.')],
    registry: Annotated[Path, typer.Option('--registry')] = DEFAULT_REGISTRY,
    lock: Annotated[Path, typer.Option('--lock')] = DEFAULT_LOCK,
    artifact_root: Annotated[Path, typer.Option('--artifact-root')] = DEFAULT_ARTIFACT_ROOT,
    replace: Annotated[bool, typer.Option('--replace')] = False,
    confirm_family: Annotated[str | None, typer.Option('--confirm-family')] = None,
) -> None:
    try:
        record = lock_artifact_service(
            family_id=family, registry_path=registry, lock_path=lock,
            artifact_root=artifact_root, file=file, source_url=source_url,
            retrieved_at=retrieved_at, replace=replace, confirm_family=confirm_family,
        )
        _emit({
            'status': 'ok', 'family_id': record.family_id, 'artifact_path': record.artifact_path,
            'size_bytes': record.size_bytes, 'sha256': record.sha256,
        })
    except (ValueError, OSError) as error:
        _fail(error)


@app.command('compare-family')
def compare_family_command(
    family: Annotated[str, typer.Argument()],
    current_bundle: Annotated[Path, typer.Option('--current-bundle')],
    output: Annotated[Path, typer.Option('--output')],
    registry: Annotated[Path, typer.Option('--registry')] = DEFAULT_REGISTRY,
    lock: Annotated[Path, typer.Option('--lock')] = DEFAULT_LOCK,
    artifact_root: Annotated[Path, typer.Option('--artifact-root')] = DEFAULT_ARTIFACT_ROOT,
) -> None:
    try:
        result = compare_family_service(
            family_id=family, registry_path=registry, lock_path=lock,
            artifact_root=artifact_root, current_bundle=current_bundle, output=output,
        )
        _emit({
            'status': 'ok', 'family_id': family,
            'report_count': result.report_count, 'output_id': result.output_id,
        })
    except (ValueError, OSError) as error:
        _fail(error)


@app.command('build-candidate')
def build_candidate_command(
    family: Annotated[str, typer.Argument()],
    report_dir: Annotated[Path, typer.Option('--report-dir')],
    output: Annotated[Path, typer.Option('--output')],
    registry: Annotated[Path, typer.Option('--registry')] = DEFAULT_REGISTRY,
    lock: Annotated[Path, typer.Option('--lock')] = DEFAULT_LOCK,
    artifact_root: Annotated[Path, typer.Option('--artifact-root')] = DEFAULT_ARTIFACT_ROOT,
    replace_from_source: Annotated[bool, typer.Option('--replace-from-source')] = False,
) -> None:
    try:
        result = build_candidate_service(
            family_id=family, registry_path=registry, lock_path=lock,
            artifact_root=artifact_root, report_dir=report_dir, output=output,
            replace_from_source=replace_from_source,
        )
        _emit({
            'status': 'ok', 'family_id': family,
            'work_count': result.work_count, 'output_id': result.output_id,
        })
    except (ValueError, OSError) as error:
        _fail(error)


if __name__ == '__main__':
    app()
