"""Validated request and response shapes for commentary APIs."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, StrictBool


Availability = Literal['available', 'no_entry', 'coverage_incomplete', 'wider_range']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ConfirmationRequest(StrictModel):
    confirm: StrictBool = False


class CommentaryCoverageWork(StrictModel):
    chapters: int
    chapter_numbers: list[int]
    chapter_numbers_complete: bool
    entries: int


class CommentaryCoverage(StrictModel):
    books: int
    chapters: int
    entries: int
    by_work: dict[str, CommentaryCoverageWork]


class CommentarySourceResponse(StrictModel):
    id: str
    title: str
    abbreviation: str
    author: str
    publication_period: str
    tradition: str
    language: str
    license_spdx: str
    license_url: str
    attribution: str
    provenance_url: str
    edition_version: int
    dataset_version: str
    coverage: CommentaryCoverage


class CommentarySourcesResponse(StrictModel):
    sources: list[CommentarySourceResponse]


class CommentaryScope(StrictModel):
    verse_start: int | None
    verse_end: int | None


class CommentaryEntryResponse(StrictModel):
    scope: CommentaryScope
    entry_type: Literal['book_intro', 'chapter_intro', 'verse', 'verse_range']
    heading: str | None
    body: str
    source_locator: str
    citation: str
    source: CommentarySourceResponse


class CommentaryReference(StrictModel):
    book: str
    chapter: int
    verse: int | None = None


class CommentaryEditionResponse(StrictModel):
    id: str
    version: int
    dataset_version: str


class CommentaryPassageResponse(StrictModel):
    reference: CommentaryReference
    availability: Availability
    source: CommentarySourceResponse
    edition: CommentaryEditionResponse
    coverage: CommentaryCoverage
    entries: list[CommentaryEntryResponse]
    truncated: bool
class CommentaryCompareResponse(StrictModel):
    reference: CommentaryReference
    results: list[CommentaryPassageResponse]


class CommentaryFindingResponse(StrictModel):
    severity: Literal['error', 'warning']
    code: str
    work_id: str | None
    chapter: int | None
    verse: int | None
    message: str


class CommentaryImportStatusResponse(StrictModel):
    id: str
    source_id: str
    status: Literal['staged', 'validated', 'verified', 'published', 'failed', 'rolled_back']
    staged_count: int
    error_count: int
    warning_count: int
    metadata: dict[str, Any]
    findings: list[CommentaryFindingResponse]


class CommentaryPublicationActionResponse(StrictModel):
    publication_id: int
    source_id: str
    edition_id: str
    version: int
    active: bool
