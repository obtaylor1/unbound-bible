"""Public API for deterministic scripture source verification."""

from app.library.verification.compare import compare_work
from app.library.verification.report import (
    ReportWriteResult,
    report_json_bytes,
    report_markdown,
    report_sha256,
    write_report_pair,
)
from app.library.verification.registry import (
    APPROVED_SOURCE_DEFINITIONS,
    ArtifactLock,
    ArtifactLockRecord,
    LockWriteError,
    RegistryError,
    SourceArtifactError,
    SourceDefinition,
    SourceRegistry,
    load_artifact_lock,
    load_source_registry,
    verify_artifact,
)
from app.library.verification.types import (
    ComparisonCounts,
    ComparisonRules,
    CurrentPublicationIdentity,
    DifferenceClassification,
    SourceArtifactIdentity,
    SourceVerse,
    VerseDifference,
    VersePosition,
    WorkComparisonReport,
)

__all__ = [
    'APPROVED_SOURCE_DEFINITIONS',
    'ComparisonCounts',
    'ComparisonRules',
    'CurrentPublicationIdentity',
    'DifferenceClassification',
    'ArtifactLock',
    'ArtifactLockRecord',
    'LockWriteError',
    'RegistryError',
    'ReportWriteResult',
    'SourceArtifactIdentity',
    'SourceArtifactError',
    'SourceDefinition',
    'SourceRegistry',
    'SourceVerse',
    'VerseDifference',
    'VersePosition',
    'WorkComparisonReport',
    'compare_work',
    'load_artifact_lock',
    'load_source_registry',
    'report_json_bytes',
    'report_markdown',
    'report_sha256',
    'write_report_pair',
    'verify_artifact',
]
