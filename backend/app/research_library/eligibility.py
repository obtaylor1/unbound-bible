"""Fail-closed public eligibility policy for research-library publications."""

from dataclasses import dataclass

from sqlalchemy import and_, func, or_
from sqlalchemy.sql.elements import ColumnElement

from app.research_library.models import LicenseRecord, SourceEdition, SourcePublication


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    eligible: bool
    reasons: tuple[str, ...]


def evaluate_publication(
    publication: SourcePublication,
    source_edition: SourceEdition,
    license_record: LicenseRecord | None,
) -> EligibilityDecision:
    """Evaluate scalar inputs in the stable order represented below.

    Callers must pass all three records explicitly. The evaluator never follows
    ORM relationships, so its decision is deterministic and cannot hide lazy I/O.
    """
    reasons: list[str] = []

    if publication.status != 'active':
        reasons.append('publication_not_active')
    if source_edition.active_publication_id != publication.id:
        reasons.append('publication_not_selected')
    if publication.source_edition_id != source_edition.id:
        reasons.append('edition_mismatch')
    if publication.validation_approved is not True:
        reasons.append('validation_not_approved')
    if publication.public_visibility is not True:
        reasons.append('not_public')

    if license_record is None:
        reasons.append('license_missing')
    else:
        if (
            publication.license_record_id != license_record.id
            or license_record.source_edition_id != source_edition.id
        ):
            reasons.append('license_mismatch')
        if license_record.reviewer_id is None or license_record.verification_date is None:
            reasons.append('rights_not_reviewed')
        if license_record.commercial_use_allowed is not True:
            reasons.append('commercial_use_not_allowed')
        if license_record.display_allowed is not True:
            reasons.append('display_not_allowed')
        if license_record.redistribution_allowed is not True:
            reasons.append('redistribution_not_allowed')
        if (
            license_record.attribution_required is not True
            and license_record.attribution_required is not False
        ):
            reasons.append('attribution_requirement_unknown')
        elif (
            license_record.attribution_required is True
            and not (license_record.required_attribution_text or '').strip()
        ):
            reasons.append('attribution_missing')

    return EligibilityDecision(eligible=not reasons, reasons=tuple(reasons))


def public_eligibility_predicate() -> ColumnElement[bool]:
    """Return the evaluator-equivalent gate for explicitly joined model tables."""
    return and_(
        SourcePublication.status == 'active',
        SourceEdition.active_publication_id == SourcePublication.id,
        SourcePublication.source_edition_id == SourceEdition.id,
        SourcePublication.validation_approved.is_(True),
        SourcePublication.public_visibility.is_(True),
        SourcePublication.license_record_id.is_not(None),
        SourcePublication.license_record_id == LicenseRecord.id,
        LicenseRecord.source_edition_id == SourceEdition.id,
        LicenseRecord.reviewer_id.is_not(None),
        LicenseRecord.verification_date.is_not(None),
        LicenseRecord.commercial_use_allowed.is_(True),
        LicenseRecord.display_allowed.is_(True),
        LicenseRecord.redistribution_allowed.is_(True),
        LicenseRecord.attribution_required.is_not(None),
        or_(
            LicenseRecord.attribution_required.is_(False),
            and_(
                LicenseRecord.attribution_required.is_(True),
                LicenseRecord.required_attribution_text.is_not(None),
                func.length(func.trim(LicenseRecord.required_attribution_text)) > 0,
            ),
        ),
    )
