from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app.application import create_application
from app.library.canon import navigation_works
from app.library.models import EditionCoverage, EditionWorkSource, LibraryWork, TextEdition


PROTESTANT_WORK_IDS = (
    'genesis', 'exodus', 'leviticus', 'numbers', 'deuteronomy',
    'joshua', 'judges', 'ruth', '1-samuel', '2-samuel', '1-kings', '2-kings',
    '1-chronicles', '2-chronicles', 'ezra', 'nehemiah', 'esther', 'job', 'psalms',
    'proverbs', 'ecclesiastes', 'song-of-solomon', 'isaiah', 'jeremiah',
    'lamentations', 'ezekiel', 'daniel', 'hosea', 'joel', 'amos', 'obadiah',
    'jonah', 'micah', 'nahum', 'habakkuk', 'zephaniah', 'haggai', 'zechariah',
    'malachi', 'matthew', 'mark', 'luke', 'john', 'acts', 'romans',
    '1-corinthians', '2-corinthians', 'galatians', 'ephesians', 'philippians',
    'colossians', '1-thessalonians', '2-thessalonians', '1-timothy', '2-timothy',
    'titus', 'philemon', 'hebrews', 'james', '1-peter', '2-peter', '1-john',
    '2-john', '3-john', 'jude', 'revelation',
)
CATHOLIC_WORK_IDS = (
    'genesis', 'exodus', 'leviticus', 'numbers', 'deuteronomy',
    'joshua', 'judges', 'ruth', '1-samuel', '2-samuel', '1-kings', '2-kings',
    '1-chronicles', '2-chronicles', 'ezra', 'nehemiah', 'tobit', 'judith',
    'esther', '1-maccabees', '2-maccabees', 'job', 'psalms', 'proverbs',
    'ecclesiastes', 'song-of-solomon', 'wisdom-of-solomon', 'sirach', 'isaiah',
    'jeremiah', 'lamentations', 'baruch', 'ezekiel', 'daniel', 'hosea', 'joel',
    'amos', 'obadiah', 'jonah', 'micah', 'nahum', 'habakkuk', 'zephaniah',
    'haggai', 'zechariah', 'malachi', 'matthew', 'mark', 'luke', 'john', 'acts',
    'romans', '1-corinthians', '2-corinthians', 'galatians', 'ephesians',
    'philippians', 'colossians', '1-thessalonians', '2-thessalonians', '1-timothy',
    '2-timothy', 'titus', 'philemon', 'hebrews', 'james', '1-peter', '2-peter',
    '1-john', '2-john', '3-john', 'jude', 'revelation',
)


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


def _add_composite_coverage(application, work_id='genesis', *, canon_scope='ethio81') -> None:
    with application.state.session_factory() as session:
        edition = session.get(TextEdition, 'EOTC-COMPOSITE-EN')
        if edition is None:
            session.add(TextEdition(
                edition_code='EOTC-COMPOSITE-EN',
                name='Ethiopian Orthodox Composite English',
                reading_language='English',
                source_language='Multiple',
                script='Latin',
                relationship='exact_ethiopian',
                expected_coverage={'works': [work_id]},
                verification_status='provisional',
            ))
            session.flush()
        session.add(EditionCoverage(
            edition_code='EOTC-COMPOSITE-EN',
            work_id=work_id,
            status='verified_english',
            chapter_count=50,
            verse_count=1533,
            note='Published composite fixture',
        ))
        session.add(EditionWorkSource(
            edition_code='EOTC-COMPOSITE-EN',
            work_id=work_id,
            source_key='world-messianic-bible',
            source_label='World Messianic Bible',
            translator='Michael Paul Johnson',
            source_language='Hebrew',
            source_tradition='Masoretic',
            published_year=2020,
            license_spdx='PD',
            attribution='Public-domain World Messianic Bible text.',
            provenance_url='https://ebible.org/engwmb/',
            fallback=False,
            modified=True,
            modification_note='Normalized into the application verse schema.',
            verification_status='in_progress',
            canon_scope=canon_scope,
        ))
        session.commit()


def _add_reader_fixture(application) -> None:
    with application.state.session_factory() as session:
        session.execute(text('''
            CREATE TABLE biblical_texts (
                id INTEGER PRIMARY KEY,
                book TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER NOT NULL,
                text TEXT NOT NULL,
                translation TEXT
            )
        '''))
        session.add(TextEdition(
            edition_code='GEEZ1980-RESEARCH',
            name="Ge'ez Bible (1980 EC) — Research Use",
            reading_language="Ge'ez",
            source_language="Ge'ez",
            script="Ge'ez",
            relationship='exact_ethiopian',
            expected_coverage={'works': ['genesis']},
            verification_status='verified',
            license_spdx='CC-BY-NC-ND-4.0',
            source_tradition='Ethiopian Orthodox Tewahedo',
        ))
        session.execute(text('''
            INSERT INTO biblical_texts
                (id, book, chapter, verse, text, translation)
            VALUES
                (1, 'Genesis', 1, 1, 'በቀዳሚ ገብረ እግዚአብሔር ሰማየ ወምድረ።', 'GEEZ1980-RESEARCH'),
                (2, 'Genesis', 1, 1, 'In the beginning God created the heaven and the earth.', 'KJV')
        '''))
        session.commit()


def test_modular_launcher_exposes_reader_compatibility_routes(test_settings):
    application = create_application(test_settings)
    _add_reader_fixture(application)
    client = TestClient(application)

    available = client.get('/api/biblical-texts/available-books')
    chapter = client.get('/api/biblical-texts/chapter-content?book=Genesis&chapter=1')
    book = client.get('/api/biblical-texts/book-content?book=Genesis')
    details = client.get('/api/v1/texts/Genesis/1/1/details')

    assert available.status_code == chapter.status_code == book.status_code == details.status_code == 200
    assert available.json() == {'books': ['Genesis']}
    assert len(chapter.json()['content']) == len(book.json()['content']) == 2
    geez = next(row for row in chapter.json()['content'] if row['translation'] == 'GEEZ1980-RESEARCH')
    assert geez['text'] == 'በቀዳሚ ገብረ እግዚአብሔር ሰማየ ወምድረ።'
    assert geez['edition']['name'] == "Ge'ez Bible (1980 EC) — Research Use"
    assert geez['work_source'] is None
    assert details.json()['translations']['geez1980-research'] == geez['text']


def test_reader_chapter_rows_expose_the_actual_edition_work_source(test_settings):
    application = create_application(test_settings)
    _add_reader_fixture(application)
    _add_composite_coverage(application)
    with application.state.session_factory() as session:
        session.execute(text('''
            INSERT INTO biblical_texts
                (id, book, chapter, verse, text, translation)
            VALUES
                (3, 'Genesis', 1, 2, 'The earth was formless and empty.', 'EOTC-COMPOSITE-EN')
        '''))
        session.commit()

    rows = TestClient(application).get(
        '/api/biblical-texts/chapter-content?book=Genesis&chapter=1'
    ).json()['content']
    composite = next(row for row in rows if row['translation'] == 'EOTC-COMPOSITE-EN')
    kjv = next(row for row in rows if row['translation'] == 'KJV')

    assert composite['work_source'] == {
        'source_key': 'world-messianic-bible',
        'source_label': 'World Messianic Bible',
        'translator': 'Michael Paul Johnson',
        'source_language': 'Hebrew',
        'source_tradition': 'Masoretic',
        'published_year': 2020,
        'license': 'PD',
        'attribution': 'Public-domain World Messianic Bible text.',
        'provenance_url': 'https://ebible.org/engwmb/',
        'rights_url': None,
        'rights_jurisdiction': None,
        'source_edition': None,
        'source_revision': None,
        'fallback': False,
        'modified': True,
        'modification_note': 'Normalized into the application verse schema.',
        'verification_status': 'in_progress',
        'transformations': [],
        'verification': {
            'status': 'in_progress',
            'label': 'Source verification in progress',
            'verified_at': None,
        },
        'canon_scope': 'ethio81',
    }
    assert kjv['work_source'] is None


def test_reader_edition_disclosures_use_the_same_path_redaction(test_settings):
    application = create_application(test_settings)
    _add_reader_fixture(application)
    with application.state.session_factory() as session:
        edition = session.get(TextEdition, 'GEEZ1980-RESEARCH')
        edition.name = 'Edition from /Users/admin/private/edition.txt'
        edition.reading_language = r'C:\Users\admin\language.txt'
        edition.source_language = 'file:///private/source-language.txt'
        edition.script = '%252FUsers%252Fadmin%252Fscript.txt'
        edition.publisher = 'token=do-not-disclose'
        edition.attribution = 'Generated from ~/private/attribution.txt'
        edition.provenance_url = (
            'https://example.org/?file=%252FUsers%252Fadmin%252Fsource.txt'
        )
        edition.source_tradition = 'Generated from /custom/private/tradition.txt'
        edition.versification = 'https://example.org/not-a-description'
        session.commit()

    row = next(
        row for row in TestClient(application).get(
            '/api/biblical-texts/chapter-content?book=Genesis&chapter=1'
        ).json()['content']
        if row['translation'] == 'GEEZ1980-RESEARCH'
    )

    assert row['edition'] == {
        'code': 'GEEZ1980-RESEARCH',
        'name': 'Not disclosed',
        'language': 'Not disclosed',
        'source_language': 'Not disclosed',
        'script': 'Not disclosed',
        'publisher': None,
        'license': 'CC-BY-NC-ND-4.0',
        'attribution': None,
        'provenance_url': None,
        'source_tradition': None,
        'relationship': 'exact_ethiopian',
        'versification': None,
        'verification_status': 'verified',
    }
    serialized = str(row['edition']).casefold()
    assert '/users/' not in serialized
    assert 'do-not-disclose' not in serialized


def test_reader_source_resolution_uses_book_alias_without_cross_edition_leakage(test_settings):
    application = create_application(test_settings)
    _add_reader_fixture(application)
    with application.state.session_factory() as session:
        session.add(EditionWorkSource(
            edition_code='GEEZ1980-RESEARCH',
            work_id='qalementos',
            source_key='geez-critical-text',
            source_label="Ge'ez Critical Text",
            source_language="Ge'ez",
            source_tradition='Ethiopian Orthodox Tewahedo',
            license_spdx='CC-BY-NC-ND-4.0',
            attribution='Research edition fixture.',
            fallback=False,
            modified=False,
            verification_status='verified_exact',
            canon_scope='ethio81',
        ))
        session.execute(text('''
            INSERT INTO biblical_texts
                (id, book, chapter, verse, text, translation)
            VALUES
                (3, 'Book of Clement', 1, 1, 'Alias resolution fixture.', 'GEEZ1980-RESEARCH'),
                (4, 'Book of Clement', 1, 1, 'Unregistered translation fixture.', 'KJV')
        '''))
        session.commit()

    rows = TestClient(application).get(
        '/api/biblical-texts/chapter-content', params={'book': 'Book of Clement', 'chapter': 1}
    ).json()['content']
    geez = next(row for row in rows if row['translation'] == 'GEEZ1980-RESEARCH')
    kjv = next(row for row in rows if row['translation'] == 'KJV')

    assert geez['work_source']['source_key'] == 'geez-critical-text'
    assert kjv['work_source'] is None


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
        'recommended_edition': None,
        'unavailable_reason': 'English text not yet available',
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


def test_ethiopian_catalog_matches_the_complete_authoritative_navigation_order(test_settings):
    response = _client(test_settings).get('/api/v1/books?canon=ETHIO81')

    assert response.status_code == 200
    assert [book['id'] for book in response.json()['books']] == [
        work.id for work in navigation_works()
    ]


def test_every_ethiopian_navigation_work_has_the_complete_response_shape(test_settings):
    response = _client(test_settings).get('/api/v1/books?canon=ETHIO81')

    assert response.status_code == 200
    books = response.json()['books']
    required_keys = {
        'id',
        'name',
        'testament',
        'collection',
        'entry_name',
        'entry_order',
        'canon_included',
        'coverage',
        'recommended_edition',
        'unavailable_reason',
    }
    assert len(books) == 95
    for book in books:
        assert set(book) == required_keys
        assert isinstance(book['id'], str)
        assert isinstance(book['name'], str)
        assert book['testament'] in {'Old Testament', 'New Testament'}
        assert isinstance(book['collection'], str)
        assert isinstance(book['entry_name'], str)
        assert isinstance(book['entry_order'], int) and not isinstance(book['entry_order'], bool)
        assert book['canon_included'] is True
        assert isinstance(book['coverage'], list)


def test_ethiopian_catalog_recommends_composite_only_for_covered_canonical_works(test_settings):
    application = create_application(test_settings)
    _add_verified_genesis_coverage(application)
    _add_composite_coverage(application)

    books = TestClient(application).get('/api/v1/books?canon=ETHIO81').json()['books']
    by_id = {book['id']: book for book in books}

    assert by_id['genesis']['recommended_edition'] == 'EOTC-COMPOSITE-EN'
    assert by_id['genesis']['unavailable_reason'] is None
    assert by_id['tegsats']['recommended_edition'] is None
    assert by_id['tegsats']['unavailable_reason'] == 'English text not yet available'
    assert 'prayer-of-manasseh' not in by_id


def test_ethiopian_catalog_does_not_recommend_original_language_or_supplemental_sources(test_settings):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        session.add(TextEdition(
            edition_code='ORIGINAL-ONLY',
            name="Verified Ge'ez",
            reading_language="Ge'ez",
            source_language="Ge'ez",
            script="Ge'ez",
            relationship='exact_ethiopian',
            expected_coverage={'works': ['tegsats']},
            verification_status='verified',
        ))
        session.flush()
        session.add(EditionCoverage(
            edition_code='ORIGINAL-ONLY',
            work_id='tegsats',
            status='verified_original',
            chapter_count=1,
            verse_count=1,
            note='Original-language fixture',
        ))
        session.commit()
    _add_composite_coverage(application, 'prayer-of-manasseh', canon_scope='supplemental')

    books = TestClient(application).get('/api/v1/books?canon=ETHIO81').json()['books']
    by_id = {book['id']: book for book in books}

    assert by_id['tegsats']['recommended_edition'] is None
    assert by_id['tegsats']['unavailable_reason'] == 'English text not yet available'
    assert 'prayer-of-manasseh' not in by_id


def test_verified_english_is_recommended_ahead_of_other_provisional_english(test_settings):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        for code, status in (('PROVISIONAL-EN', 'provisional'), ('VERIFIED-EN', 'verified')):
            session.add(TextEdition(
                edition_code=code,
                name=code,
                reading_language='English',
                source_language='Hebrew',
                script='Latin',
                relationship='general_reading',
                expected_coverage={'works': ['genesis']},
                verification_status=status,
            ))
            session.flush()
            session.add(EditionCoverage(
                edition_code=code,
                work_id='genesis',
                status='verified_english',
                chapter_count=50,
                verse_count=1533,
                note='Ranking fixture',
            ))
        session.commit()

    genesis = TestClient(application).get('/api/v1/books?canon=ETHIO81').json()['books'][0]

    assert genesis['recommended_edition'] == 'VERIFIED-EN'
    assert genesis['unavailable_reason'] is None


def test_ethiopian_catalog_uses_a_fixed_query_budget(test_settings):
    application = create_application(test_settings)
    statements = []

    def record_statement(*_args):
        statements.append(_args[2])

    event.listen(application.state.database_engine, 'before_cursor_execute', record_statement)
    try:
        response = TestClient(application).get('/api/v1/books?canon=ETHIO81')
    finally:
        event.remove(application.state.database_engine, 'before_cursor_execute', record_statement)

    assert not event.contains(
        application.state.database_engine, 'before_cursor_execute', record_statement
    )
    assert response.status_code == 200
    assert len(response.json()['books']) == 95
    assert 1 <= len(statements) <= 4


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


def test_standard_catalogs_have_complete_unique_canonical_order(test_settings):
    client = _client(test_settings)

    protestant_ids = [
        book['id'] for book in client.get('/api/v1/books?canon=PROT66').json()['books']
    ]
    catholic_ids = [
        book['id'] for book in client.get('/api/v1/books?canon=CATH73').json()['books']
    ]

    assert protestant_ids == list(PROTESTANT_WORK_IDS)
    assert catholic_ids == list(CATHOLIC_WORK_IDS)
    assert len(protestant_ids) == len(set(protestant_ids)) == 66
    assert len(catholic_ids) == len(set(catholic_ids)) == 73


def test_every_standard_catalog_id_resolves_to_a_library_work_detail(test_settings):
    client = _client(test_settings)

    for work_id in dict.fromkeys((*PROTESTANT_WORK_IDS, *CATHOLIC_WORK_IDS)):
        response = client.get(f'/api/v1/library/works/{work_id}')
        assert response.status_code == 200, work_id
        assert response.json()['id'] == work_id


def test_maccabees_aliases_and_installed_coverage_are_available(test_settings):
    application = create_application(test_settings)
    with application.state.session_factory() as session:
        assert session.get(LibraryWork, '1-maccabees') is not None
        assert session.get(LibraryWork, '2-maccabees') is not None
        session.add(TextEdition(
            edition_code='CATHOLIC-TEST',
            name='Catholic Test Edition',
            reading_language='English',
            source_language='Greek',
            script='Latin',
            relationship='general_reading',
            expected_coverage={'works': ['1-maccabees', '2-maccabees']},
            verification_status='verified',
        ))
        session.flush()
        session.add_all((
            EditionCoverage(
                edition_code='CATHOLIC-TEST',
                work_id='1-maccabees',
                status='verified_english',
                chapter_count=16,
                verse_count=922,
                note='Catholic catalog regression fixture',
            ),
            EditionCoverage(
                edition_code='CATHOLIC-TEST',
                work_id='2-maccabees',
                status='verified_english',
                chapter_count=15,
                verse_count=556,
                note='Catholic catalog regression fixture',
            ),
        ))
        session.commit()

    client = TestClient(application)
    first = client.get('/api/v1/library/works/1-maccabees')
    second = client.get('/api/v1/library/works/2-maccabees')

    assert first.status_code == second.status_code == 200
    assert first.json()['aliases'] == ['1 maccabees', 'i maccabees']
    assert second.json()['aliases'] == ['2 maccabees', 'ii maccabees']
    assert first.json()['coverage'][0]['edition_code'] == 'CATHOLIC-TEST'
    assert second.json()['coverage'][0]['edition_code'] == 'CATHOLIC-TEST'


def test_books_reject_unknown_canon_and_responses_are_stable(test_settings):
    client = _client(test_settings)

    first = client.get('/api/v1/books?canon=ETHIO81')
    second = client.get('/api/v1/books?canon=ETHIO81')
    unknown = client.get('/api/v1/books?canon=NOT-A-CANON')

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert unknown.status_code == 422
    assert 'Unknown canon' in unknown.json()['detail']
