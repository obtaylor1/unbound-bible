"""Strict, bounded response shapes for scripture source verification APIs."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


VerificationStatus = Literal[
    'in_progress',
    'verified_exact',
    'verified_formatting',
    'verified_rebuilt',
    'review_required',
]

VERIFICATION_LABELS: dict[VerificationStatus, str] = {
    'in_progress': 'Source verification in progress',
    'verified_exact': 'Source verified',
    'verified_formatting': 'Verified with documented formatting changes',
    'verified_rebuilt': 'Rebuilt from verified source',
    'review_required': 'Source review required',
}

ShortText = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Identifier = Annotated[
    str,
    StringConstraints(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]*$'),
]
PublicUrl = Annotated[str, StringConstraints(min_length=1, max_length=2048)]
LongText = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
Timestamp = Annotated[
    str,
    StringConstraints(
        max_length=32,
        pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$',
    ),
]
Sha256 = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
TransformationDescription = Annotated[
    str, StringConstraints(min_length=1, max_length=300)
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class VerificationSummary(StrictModel):
    status: VerificationStatus
    label: ShortText
    verified_at: Timestamp | None


class PublicWorkSourceResponse(StrictModel):
    edition_code: Identifier
    work_id: Identifier
    source_key: Identifier
    source_label: ShortText
    translator: ShortText | None
    source_language: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    source_tradition: ShortText
    published_year: Annotated[int, Field(ge=1, le=9999)] | None
    license: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    attribution: LongText
    provenance_url: PublicUrl | None
    rights_url: PublicUrl | None
    rights_jurisdiction: Annotated[str, StringConstraints(min_length=1, max_length=500)] | None
    source_edition: ShortText | None
    source_revision: ShortText | None
    fallback: bool
    modified: bool
    modification_note: LongText | None
    transformations: Annotated[list[TransformationDescription], Field(max_length=8)]
    canon_scope: Literal['ethio81', 'supplemental']
    verification: VerificationSummary


class VerificationComparisonTotals(StrictModel):
    exact: Annotated[int, Field(ge=0)]
    formatting: Annotated[int, Field(ge=0)]
    missing: Annotated[int, Field(ge=0)]
    extra: Annotated[int, Field(ge=0)]
    wording: Annotated[int, Field(ge=0)]


class AdminWorkVerificationResponse(StrictModel):
    work_id: Identifier
    work_name: ShortText
    source_key: Identifier
    source_label: ShortText
    source_edition: ShortText | None
    source_revision: ShortText | None
    provenance_url: PublicUrl | None
    rights_url: PublicUrl | None
    license: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    fallback: bool
    canon_scope: Literal['ethio81', 'supplemental']
    artifact_sha256: Sha256 | None
    comparison_report_sha256: Sha256 | None
    comparison: VerificationComparisonTotals
    reviewer: ShortText | None
    reviewed_at: Timestamp | None
    verification: VerificationSummary


class VerificationFamilyTotal(StrictModel):
    source_key: Identifier
    count: Annotated[int, Field(ge=0, le=100)]


class VerificationStatusTotal(StrictModel):
    status: VerificationStatus
    label: ShortText
    count: Annotated[int, Field(ge=0, le=100)]


class AdminVerificationInventoryResponse(StrictModel):
    edition_code: Identifier
    total_works: Annotated[int, Field(ge=0, le=100)]
    family_totals: Annotated[list[VerificationFamilyTotal], Field(max_length=20)]
    status_totals: Annotated[list[VerificationStatusTotal], Field(max_length=5)]
    works: Annotated[list[AdminWorkVerificationResponse], Field(max_length=100)]
