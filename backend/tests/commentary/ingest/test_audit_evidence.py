from uuid import uuid4

import pytest

from app.commentary.ingest.types import NormalizedCommentaryEntry


def _rows():
    return [
        NormalizedCommentaryEntry(
            '1-chronicles', None, None, None, 'book_intro', None, 'Book introduction.',
            'helloao:john-gill:1CH:book-intro', 0,
        ),
        NormalizedCommentaryEntry(
            '1-chronicles', 10, None, None, 'chapter_intro', None,
            'Chapter introduction.', 'helloao:john-gill:1CH:chapter:10:intro', 1,
        ),
        NormalizedCommentaryEntry(
            '1-chronicles', 10, 1, 1, 'verse', None, 'First note.',
            'helloao:john-gill:1CH:chapter:10:verse:1', 2,
        ),
        NormalizedCommentaryEntry(
            '1-chronicles', 12, 1, 2, 'verse_range', None, 'Second note.',
            'helloao:john-gill:1CH:chapter:12:verse:1-2', 3,
        ),
    ]


def _provider_audit(**overrides):
    value = {
        'provider_book_count': 1,
        'provider_chapter_count': 3,
        'provider_content_record_count': 3,
        'acquired_normalized_entry_count': 4,
        'normalized_entry_type_counts': {
            'book_intro': 1, 'chapter_intro': 1, 'verse': 1, 'verse_range': 1,
        },
        'reviewed_exclusion_count': 1,
        'covered_normalized_chapter_count': 2,
        'empty_provider_chapters': [
            {'source_book_id': '1CH', 'work_id': '1-chronicles', 'chapter': 11},
        ],
    }
    value.update(overrides)
    return value


def test_provider_audit_reconciles_intros_exclusion_and_john_gill_empty_chapter():
    from app.commentary.ingest.publish import reconcile_provider_audit

    result = reconcile_provider_audit(_provider_audit(), _rows())

    assert result['expected_normalized_entry_count'] == 4
    assert result['variance'] == 0
    assert result['formula'] == (
        'normalized entries = provider content records - reviewed exclusions '
        '+ book introductions + chapter introductions'
    )
    assert result['empty_provider_chapters'] == [
        {'source_book_id': '1CH', 'work_id': '1-chronicles', 'chapter': 11},
    ]


@pytest.mark.parametrize('mutation', [
    {'provider_content_record_count': 4},
    {'acquired_normalized_entry_count': 5},
    {'covered_normalized_chapter_count': 3},
    {'empty_provider_chapters': []},
    {'normalized_entry_type_counts': {
        'book_intro': 1, 'chapter_intro': 1, 'verse': 2, 'verse_range': 0,
    }},
])
def test_provider_audit_rejects_count_or_coverage_tampering(mutation):
    from app.commentary.ingest.publish import reconcile_provider_audit

    with pytest.raises(ValueError, match='provider audit'):
        reconcile_provider_audit(_provider_audit(**mutation), _rows())


def test_warning_review_policy_acknowledges_only_the_three_reviewed_codes():
    from app.commentary.ingest.publish import warning_review_snapshot

    review = warning_review_snapshot({
        'missing_chapter_intro': 1700,
        'multiple_notes_at_anchor': 50,
        'reviewed_exclusion': 1,
    })

    assert review['warning_count'] == 1751
    assert review['acknowledged_warning_count'] == 1751
    assert review['all_warnings_reviewed'] is True
    assert set(review['counts_by_code']) == {
        'missing_chapter_intro', 'multiple_notes_at_anchor', 'reviewed_exclusion',
    }
    assert review['dispositions_by_code']['missing_chapter_intro']['disposition'] == 'accepted'


def test_warning_review_policy_rejects_unknown_warning_code():
    from app.commentary.ingest.publish import warning_review_snapshot

    with pytest.raises(ValueError, match='no reviewed disposition'):
        warning_review_snapshot({'style': 1})


def test_validate_run_persists_reconciled_audit_and_warning_acknowledgment(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import stage_bundle, validate_run

    rows = [
        NormalizedCommentaryEntry(
            'genesis', None, None, None, 'book_intro', None, 'Book introduction.',
            'helloao:matthew-henry:GEN:book-intro', 0,
        ),
        NormalizedCommentaryEntry(
            'genesis', 1, 1, 1, 'verse', None, 'A note.',
            'helloao:matthew-henry:GEN:chapter:1:verse:1', 1,
        ),
    ]
    audit = {
        'provider_book_count': 1, 'provider_chapter_count': 1,
        'provider_content_record_count': 1, 'acquired_normalized_entry_count': 2,
        'normalized_entry_type_counts': {
            'book_intro': 1, 'chapter_intro': 0, 'verse': 1, 'verse_range': 0,
        },
        'reviewed_exclusion_count': 0, 'covered_normalized_chapter_count': 1,
        'empty_provider_chapters': [],
    }
    run = stage_bundle(
        commentary_session, source_id=commentary_source.id, source_checksum='a' * 64,
        metadata_snapshot={
            'expected_books': ['genesis'], 'provider_audit': audit,
            'reviewed_exclusion_count': 0, 'reviewed_exclusions': [],
        },
        rows=rows,
    )

    validate_run(commentary_session, run.id)

    assert run.status == 'verified'
    assert run.metadata_snapshot['provider_audit']['variance'] == 0
    assert run.metadata_snapshot['warning_review']['counts_by_code'] == {
        'missing_chapter_intro': 1,
    }
    assert run.metadata_snapshot['warning_review']['acknowledged_warning_count'] == 1


def test_audited_validation_rejects_warning_without_reviewed_policy(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import stage_bundle, validate_run

    row = NormalizedCommentaryEntry(
        'genesis', 1, 1, 1, 'verse', None, 'A note.',
        'helloao:matthew-henry:GEN:chapter:1:verse:1', 0,
    )
    run = stage_bundle(
        commentary_session, source_id=commentary_source.id, source_checksum='a' * 64,
        metadata_snapshot={
            'expected_books': ['genesis'],
            'provider_audit': {
                'provider_book_count': 1, 'provider_chapter_count': 1,
                'provider_content_record_count': 1,
                'acquired_normalized_entry_count': 1,
                'normalized_entry_type_counts': {
                    'book_intro': 0, 'chapter_intro': 0, 'verse': 1, 'verse_range': 0,
                },
                'reviewed_exclusion_count': 0,
                'covered_normalized_chapter_count': 1,
                'empty_provider_chapters': [],
            },
            'reviewed_exclusion_count': 0, 'reviewed_exclusions': [],
        },
        rows=[row],
    )

    with pytest.raises(ValueError, match='missing_book_intro.*no reviewed disposition'):
        validate_run(commentary_session, run.id)


def test_report_reconciles_warning_rows_and_rejects_tampered_snapshot(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.cli import _build_report
    from app.commentary.ingest.publish import (
        reconcile_provider_audit, warning_review_snapshot,
    )
    from app.commentary.models import CommentaryImportRun, CommentaryValidationFinding

    warning_review = warning_review_snapshot({
        'missing_chapter_intro': 1, 'reviewed_exclusion': 1,
    })
    run = CommentaryImportRun(
        id=uuid4(), source_id=commentary_source.id, source_checksum='a' * 64,
        metadata_snapshot={
            'provider_audit': reconcile_provider_audit(_provider_audit(), _rows()),
            'warning_review': warning_review,
            'reviewed_exclusion_count': 1,
            'reviewed_exclusions': [],
            'coverage': {'books': 1, 'chapters': 2, 'entries': 4, 'by_work': {}},
        },
        status='verified', staged_count=4, warning_count=2,
    )
    commentary_session.add(run)
    commentary_session.flush()
    commentary_session.add(CommentaryValidationFinding(
        run_id=run.id, severity='warning', code='missing_chapter_intro',
        message='Chapter has no introduction.', work_id='1-chronicles', chapter=12,
    ))
    commentary_session.add(CommentaryValidationFinding(
        run_id=run.id, severity='warning', code='reviewed_exclusion',
        message='A checksum-bound record was excluded.',
    ))
    commentary_session.flush()

    report = _build_report(commentary_session, run.id)
    assert report['provider_audit']['variance'] == 0
    assert report['warning_review']['acknowledged_warning_count'] == 2
    assert report['warning_review']['counts_by_code'] == {
        'missing_chapter_intro': 1, 'reviewed_exclusion': 1,
    }

    run.warning_count = 3
    commentary_session.flush()
    with pytest.raises(ValueError, match='warning counts'):
        _build_report(commentary_session, run.id)
