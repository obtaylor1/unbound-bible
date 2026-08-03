from fastapi.testclient import TestClient

from app.application import create_application
from app.library.models import EditionCoverage, TextEdition


def _client(test_settings) -> TestClient:
    return TestClient(create_application(test_settings))


def _add_verified_genesis_coverage(application) -> None:
    with application.state.session_factory() as session:
        session.add(TextEdition(
            edition_code='TEST-EN',
            name='Test English Edition',
            reading_language='English',
            source_language='Ge\'ez',
            script='Latin',
            relationship='exact_ethiopian',
            expected_coverage={'works': ['genesis']},
            verification_status='verified',
        ))
        session.flush()
        session.add(EditionCoverage(
            edition_code='TEST-EN',
            work_id='genesis',
            status='verified_english',
            chapter_count=50,
            verse_count=1533,
            note='Route fixture',
        ))
        session.commit()


def test_ethiopian_books_are_seeded_without_installed_text_coverage(test_settings):
    client = _client(test_settings)

    response = client.get('/api/v1/books?canon=eth81')

    assert response.status_code == 200
    body = response.json()
    assert body['canon_filter'] == 'ETHIO81'
    assert body['canon_count'] == 81
    assert body['navigation_count'] == 95
    genesis = body['books'][0]
    assert genesis == {
        'id': 'genesis',
        'name': 'Genesis',
        'testament': 'Old Testament',
        'collection': 'Law',
        'entry_name': 'Genesis',
        'entry_order': 1,
        'canon_included': True,
        'coverage': [],
    }


def test_ethiopian_book_order_uses_immutable_composite_work_order(test_settings):
    client = _client(test_settings)

    response = client.get('/api/v1/books?canon=ETHIO81')

    assert response.status_code == 200
    books = response.json()['books']
    assert books[-1]['id'] == 'didesqelya'
    daniel_index = next(index for index, book in enumerate(books) if book['id'] == 'daniel')
    assert [book['id'] for book in books[daniel_index:daniel_index + 4]] == [
        'daniel',
        'prayer-of-azariah',
        'susanna',
        'bel-and-the-dragon',
    ]
    assert {book['entry_name'] for book in books[daniel_index:daniel_index + 4]} == {'Daniel'}
    assert {book['entry_order'] for book in books[daniel_index:daniel_index + 4]} == {32}


def test_catalog_includes_installed_coverage_with_truthful_metadata(test_settings):
    application = create_application(test_settings)
    _add_verified_genesis_coverage(application)
    client = TestClient(application)

    response = client.get('/api/v1/books?canon=ETHIO81')

    assert response.status_code == 200
    genesis = response.json()['books'][0]
    assert genesis['coverage'] == [{
        'edition_code': 'TEST-EN',
        'edition_name': 'Test English Edition',
        'reading_language': 'English',
        'relationship': 'exact_ethiopian',
        'verification_status': 'verified',
        'status': 'verified_english',
        'chapter_count': 50,
        'verse_count': 1533,
        'note': 'Route fixture',
    }]


def test_work_detail_returns_persisted_aliases_canon_membership_and_coverage(test_settings):
    application = create_application(test_settings)
    _add_verified_genesis_coverage(application)
    client = TestClient(application)

    response = client.get('/api/v1/library/works/genesis')

    assert response.status_code == 200
    assert response.json() == {
        'id': 'genesis',
        'name': 'Genesis',
        'aliases': ['genesis'],
        'canon_entries': [{
            'canon_code': 'ETHIO81',
            'testament': 'Old Testament',
            'collection': 'Law',
            'entry_name': 'Genesis',
            'entry_order': 1,
        }],
        'coverage': [{
            'edition_code': 'TEST-EN',
            'edition_name': 'Test English Edition',
            'reading_language': 'English',
            'relationship': 'exact_ethiopian',
            'verification_status': 'verified',
            'status': 'verified_english',
            'chapter_count': 50,
            'verse_count': 1533,
            'note': 'Route fixture',
        }],
    }


def test_work_detail_preserves_composite_membership_and_404s_for_unknown_work(test_settings):
    client = _client(test_settings)

    response = client.get('/api/v1/library/works/susanna')

    assert response.status_code == 200
    assert response.json()['canon_entries'] == [{
        'canon_code': 'ETHIO81',
        'testament': 'Old Testament',
        'collection': 'Prophets',
        'entry_name': 'Daniel',
        'entry_order': 32,
    }]
    missing = client.get('/api/v1/library/works/not-a-work')
    assert missing.status_code == 404
    assert missing.json()['detail'] == 'Library work not found'


def test_protestant_and_catholic_catalogs_use_their_own_membership(test_settings):
    client = _client(test_settings)

    protestant = client.get('/api/v1/books?canon=PROT66')
    catholic = client.get('/api/v1/books?canon=CATH73')

    assert protestant.status_code == catholic.status_code == 200
    assert protestant.json()['canon_count'] == protestant.json()['navigation_count'] == 66
    assert catholic.json()['canon_count'] == catholic.json()['navigation_count'] == 73
    assert 'jubilees' not in {book['id'] for book in protestant.json()['books']}
    assert 'jubilees' not in {book['id'] for book in catholic.json()['books']}
    assert {'1-maccabees', '2-maccabees'} <= {book['id'] for book in catholic.json()['books']}


def test_books_reject_unknown_canon_and_responses_are_stable(test_settings):
    client = _client(test_settings)

    first = client.get('/api/v1/books?canon=ETHIO81')
    second = client.get('/api/v1/books?canon=ETHIO81')
    unknown = client.get('/api/v1/books?canon=NOT-A-CANON')

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert unknown.status_code == 422
    assert 'Unknown canon' in unknown.json()['detail']
