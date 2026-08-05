"""Validated request and response shapes for commentary APIs."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool


Availability = Literal['available', 'no_entry', 'coverage_incomplete', 'wider_range']


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    confirm: StrictBool = False


class CommentarySourceResponse(BaseModel):
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
    coverage: dict


class CommentaryEntryResponse(BaseModel):
    scope: dict[str, int | None]
    entry_type: str
    heading: str | None
    body: str
    source_locator: str
    citation: str
    source: CommentarySourceResponse


class CommentaryPassageResponse(BaseModel):
    reference: dict[str, str | int]
    availability: Availability
    source: CommentarySourceResponse
    edition: dict[str, str | int]
    coverage: dict
    entries: list[CommentaryEntryResponse]
    truncated: bool
