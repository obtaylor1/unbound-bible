"""Fail-closed public eligibility policy for research-library publications."""

from dataclasses import dataclass

from sqlalchemy import and_, func, inspect, or_
from sqlalchemy.orm.attributes import NO_VALUE
from sqlalchemy.orm.util import AliasedClass
from sqlalchemy.sql.elements import ColumnElement

from app.research_library.models import LicenseRecord, SourceEdition, SourcePublication


ASCII_WHITESPACE = ' \t\n\r\f\v'


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    eligible: bool
    reasons: tuple[str, ...]


def _loaded_scalar(record: object, attribute: str) -> object:
    """Read already-present ORM state without invoking a loader."""
    return inspect(record).attrs[attribute].loaded_value


def evaluate_publication(
    publication: SourcePublication,
    source_edition: SourceEdition,
    license_record: LicenseRecord | None,
) -> EligibilityDecision:
    """Evaluate scalar inputs in the stable order represented below.

    Callers must pass all three records explicitly. The evaluator reads only
    loaded scalar state, so unavailable values fail closed without hidden I/O.
    """
    reasons: list[str] = []
    publication_status = _loaded_scalar(publication, 'status')
    publication_id = _loaded_scalar(publication, 'id')
    active_publication_id = _loaded_scalar(source_edition, 'active_publication_id')
    publication_edition_id = _loaded_scalar(publication, 'source_edition_id')
    edition_id = _loaded_scalar(source_edition, 'id')
    validation_approved = _loaded_scalar(publication, 'validation_approved')
    public_visibility = _loaded_scalar(publication, 'public_visibility')

    if publication_status is NO_VALUE or publication_status != 'active':
        reasons.append('publication_not_active')
    if (
        publication_id is NO_VALUE
        or publication_id is None
        or active_publication_id is NO_VALUE
        or active_publication_id is None
        or active_publication_id != publication_id
    ):
        reasons.append('publication_not_selected')
    if (
        publication_edition_id is NO_VALUE
        or publication_edition_id is None
        or edition_id is NO_VALUE
        or edition_id is None
        or publication_edition_id != edition_id
    ):
        reasons.append('edition_mismatch')
    if validation_approved is not True:
        reasons.append('validation_not_approved')
    if public_visibility is not True:
        reasons.append('not_public')

    if license_record is None:
        reasons.append('license_missing')
    else:
        publication_license_id = _loaded_scalar(publication, 'license_record_id')
        license_id = _loaded_scalar(license_record, 'id')
        license_edition_id = _loaded_scalar(license_record, 'source_edition_id')
        if (
            publication_license_id is NO_VALUE
            or publication_license_id is None
            or license_id is NO_VALUE
            or license_id is None
            or license_edition_id is NO_VALUE
            or license_edition_id is None
            or edition_id is NO_VALUE
            or edition_id is None
            or publication_edition_id is NO_VALUE
            or publication_edition_id is None
            or publication_license_id != license_id
            or license_edition_id != edition_id
            or license_edition_id != publication_edition_id
        ):
            reasons.append('license_mismatch')
        reviewer_id = _loaded_scalar(license_record, 'reviewer_id')
        verification_date = _loaded_scalar(license_record, 'verification_date')
        if (
            reviewer_id is NO_VALUE
            or reviewer_id is None
            or verification_date is NO_VALUE
            or verification_date is None
        ):
            reasons.append('rights_not_reviewed')
        commercial_use_allowed = _loaded_scalar(
            license_record, 'commercial_use_allowed'
        )
        display_allowed = _loaded_scalar(license_record, 'display_allowed')
        redistribution_allowed = _loaded_scalar(
            license_record, 'redistribution_allowed'
        )
        attribution_required = _loaded_scalar(
            license_record, 'attribution_required'
        )
        if commercial_use_allowed is not True:
            reasons.append('commercial_use_not_allowed')
        if display_allowed is not True:
            reasons.append('display_not_allowed')
        if redistribution_allowed is not True:
            reasons.append('redistribution_not_allowed')
        if (
            attribution_required is not True
            and attribution_required is not False
        ):
            reasons.append('attribution_requirement_unknown')
        elif attribution_required is True:
            attribution_text = _loaded_scalar(
                license_record, 'required_attribution_text'
            )
            if (
                attribution_text is NO_VALUE
                or attribution_text is None
                or not attribution_text.strip(ASCII_WHITESPACE)
            ):
                reasons.append('attribution_missing')

    return EligibilityDecision(eligible=not reasons, reasons=tuple(reasons))


def public_eligibility_predicate(
    publication_entity: type[SourcePublication] | AliasedClass = SourcePublication,
    edition_entity: type[SourceEdition] | AliasedClass = SourceEdition,
    license_entity: type[LicenseRecord] | AliasedClass = LicenseRecord,
) -> ColumnElement[bool]:
    """Return the evaluator-equivalent gate for explicitly joined model tables."""
    attribution_without_ascii_control_whitespace = (
        license_entity.required_attribution_text
    )
    for whitespace in ASCII_WHITESPACE[1:]:
        attribution_without_ascii_control_whitespace = func.replace(
            attribution_without_ascii_control_whitespace,
            whitespace,
            '',
        )

    return and_(
        publication_entity.status == 'active',
        publication_entity.id.is_not(None),
        edition_entity.active_publication_id.is_not(None),
        edition_entity.active_publication_id == publication_entity.id,
        publication_entity.source_edition_id.is_not(None),
        edition_entity.id.is_not(None),
        publication_entity.source_edition_id == edition_entity.id,
        publication_entity.validation_approved.is_(True),
        publication_entity.public_visibility.is_(True),
        publication_entity.license_record_id.is_not(None),
        license_entity.id.is_not(None),
        publication_entity.license_record_id == license_entity.id,
        license_entity.source_edition_id.is_not(None),
        license_entity.source_edition_id == edition_entity.id,
        license_entity.source_edition_id == publication_entity.source_edition_id,
        license_entity.reviewer_id.is_not(None),
        license_entity.verification_date.is_not(None),
        license_entity.commercial_use_allowed.is_(True),
        license_entity.display_allowed.is_(True),
        license_entity.redistribution_allowed.is_(True),
        license_entity.attribution_required.is_not(None),
        or_(
            license_entity.attribution_required.is_(False),
            and_(
                license_entity.attribution_required.is_(True),
                license_entity.required_attribution_text.is_not(None),
                func.length(
                    func.trim(attribution_without_ascii_control_whitespace)
                )
                > 0,
            ),
        ),
    )
