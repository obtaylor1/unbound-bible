from dataclasses import FrozenInstanceError

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.research.retrieval import ResearchEvidence, retrieve_research_evidence
from app.research.schemas import ResearchDepth, SourceScope


@pytest.fixture
def research_session():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text('''
            CREATE TABLE biblical_texts (
                id INTEGER PRIMARY KEY,
                book TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER NOT NULL,
                text TEXT NOT NULL,
                translation TEXT
            )
        '''))
        connection.execute(text('''
            CREATE TABLE text_editions (
                edition_code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                reading_language TEXT NOT NULL,
                source_language TEXT NOT NULL,
                source_tradition TEXT,
                relationship TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                published_year INTEGER
            )
        '''))
        connection.execute(text('''
            CREATE TABLE edition_work_sources (
                id INTEGER PRIMARY KEY,
                edition_code TEXT NOT NULL,
                work_id TEXT NOT NULL,
                source_label TEXT NOT NULL,
                source_language TEXT NOT NULL,
                source_tradition TEXT NOT NULL,
                published_year INTEGER,
                verification_status TEXT NOT NULL,
                canon_scope TEXT NOT NULL
            )
        '''))
    with Session(engine) as session:
        yield session
    engine.dispose()


def insert_verses(session, rows):
    session.execute(text('''
        INSERT INTO biblical_texts
            (id, book, chapter, verse, text, translation)
        VALUES (:id, :book, :chapter, :verse, :text, :translation)
    '''), rows)
    session.commit()


def add_ethiopian_edition(
    session,
    *,
    edition='EOTC-COMPOSITE-EN',
    work_id='1-enoch',
    status='verified',
    canon_scope='ethio81',
    edition_tradition='Composite English sources associated with ETHIO81 works',
    relationship='general_reading',
    source_language='Ethiopic and Greek',
    source_tradition='Ethiopic Enoch',
):
    session.execute(text('''
        INSERT OR IGNORE INTO text_editions
            (edition_code, name, reading_language, source_language,
             source_tradition, relationship, verification_status, published_year)
        VALUES
            (:edition, 'Ethiopian Orthodox Composite English', 'English', 'Mixed',
             :edition_tradition, :relationship, :status, 2024)
    '''), {
        'edition': edition,
        'edition_tradition': edition_tradition,
        'relationship': relationship,
        'status': status,
    })
    session.execute(text('''
        INSERT INTO edition_work_sources
            (edition_code, work_id, source_label, source_language,
             source_tradition, published_year, verification_status, canon_scope)
        VALUES
            (:edition, :work_id, 'Verified Ethiopian source', :source_language,
             :source_tradition, 2024, :status, :canon_scope)
    '''), {
        'edition': edition,
        'work_id': work_id,
        'source_language': source_language,
        'source_tradition': source_tradition,
        'status': status,
        'canon_scope': canon_scope,
    })
    session.commit()


def test_research_evidence_is_immutable():
    evidence = ResearchEvidence(
        id='scripture:1',
        title='KJV — Genesis 1:1',
        reference='Genesis 1:1',
        text='In the beginning',
        source_type='canonical-scripture',
        tradition='Protestant',
    )

    with pytest.raises(FrozenInstanceError):
        evidence.score = 1.0


def test_biblical_canon_excludes_ethiopian_ancient_and_commentary_rows(research_session):
    insert_verses(research_session, [
        {'id': 1, 'book': 'Genesis', 'chapter': 1, 'verse': 1, 'text': 'creation beginning light', 'translation': 'KJV'},
        {'id': 2, 'book': '1 Enoch', 'chapter': 1, 'verse': 1, 'text': 'creation beginning watchers', 'translation': 'EOTC-COMPOSITE-EN'},
        {'id': 3, 'book': 'Antiquities', 'chapter': 1, 'verse': 1, 'text': 'creation ancient account', 'translation': 'JOSEPHUS'},
        {'id': 4, 'book': 'Genesis', 'chapter': 1, 'verse': 2, 'text': 'creation commentary opinion', 'translation': 'COMMENTARY'},
    ])
    add_ethiopian_edition(research_session)

    evidence = retrieve_research_evidence(
        research_session, 'creation', [SourceScope.BIBLICAL_CANON], ResearchDepth.STUDY
    )

    assert [(item.id, item.source_type, item.tradition) for item in evidence] == [
        ('scripture:1', 'canonical-scripture', 'Protestant')
    ]


def test_ethiopian_scope_returns_only_eligible_ethiopian_records(research_session):
    insert_verses(research_session, [
        {'id': 1, 'book': 'Genesis', 'chapter': 1, 'verse': 1, 'text': 'covenant creation', 'translation': 'KJV'},
        {'id': 2, 'book': '1 Enoch', 'chapter': 1, 'verse': 1, 'text': 'covenant watchers', 'translation': 'EOTC-COMPOSITE-EN'},
        {'id': 3, 'book': 'Antiquities', 'chapter': 1, 'verse': 1, 'text': 'covenant history', 'translation': 'JOSEPHUS'},
        {'id': 4, 'book': 'Jubilees', 'chapter': 1, 'verse': 1, 'text': 'astronomy calendar cycles', 'translation': 'EOTC-COMPOSITE-EN'},
    ])
    add_ethiopian_edition(research_session)
    add_ethiopian_edition(
        research_session,
        work_id='jubilees',
        source_tradition='Ethiopic Jubilees',
    )

    evidence = retrieve_research_evidence(
        research_session, 'covenant', [SourceScope.ETHIOPIAN_TRADITION], ResearchDepth.QUICK
    )

    assert len(evidence) == 1
    assert evidence[0].id == 'scripture:2'
    assert evidence[0].source_type == 'ethiopian-canon'
    assert evidence[0].tradition == 'Ethiopic Enoch'
    assert evidence[0].original_language == 'Ethiopic and Greek'


def test_unknown_general_reading_edition_fails_closed(research_session):
    insert_verses(research_session, [{
        'id': 1,
        'book': '1 Enoch',
        'chapter': 1,
        'verse': 1,
        'text': 'watchers testimony',
        'translation': 'UNKNOWN-COMPOSITE',
    }])
    add_ethiopian_edition(
        research_session,
        edition='UNKNOWN-COMPOSITE',
    )

    assert retrieve_research_evidence(
        research_session,
        'watchers',
        [SourceScope.ETHIOPIAN_TRADITION],
        ResearchDepth.QUICK,
    ) == []


def test_multiple_scopes_permit_relevant_records_without_unrelated_sources(research_session):
    insert_verses(research_session, [
        {'id': 1, 'book': 'Genesis', 'chapter': 1, 'verse': 1, 'text': 'shared covenant', 'translation': 'KJV'},
        {'id': 2, 'book': '1 Enoch', 'chapter': 1, 'verse': 1, 'text': 'shared covenant', 'translation': 'EOTC-COMPOSITE-EN'},
        {'id': 3, 'book': 'Antiquities', 'chapter': 1, 'verse': 1, 'text': 'shared covenant', 'translation': 'JOSEPHUS'},
    ])
    add_ethiopian_edition(research_session)

    evidence = retrieve_research_evidence(
        research_session,
        'shared covenant',
        [SourceScope.BIBLICAL_CANON, SourceScope.ETHIOPIAN_TRADITION],
        ResearchDepth.STUDY,
    )

    assert {item.id for item in evidence} == {'scripture:1', 'scripture:2'}
    assert {item.source_type for item in evidence} == {
        'canonical-scripture', 'ethiopian-canon'
    }


def test_multiple_scopes_do_not_force_one_result_from_each_scope(research_session):
    insert_verses(research_session, [
        {
            'id': 1,
            'book': 'Romans',
            'chapter': 6,
            'verse': 5,
            'text': 'resurrection hope and new life',
            'translation': 'KJV',
        },
        {
            'id': 2,
            'book': '1 Enoch',
            'chapter': 1,
            'verse': 1,
            'text': 'watchers and astronomy',
            'translation': 'EOTC-COMPOSITE-EN',
        },
    ])
    add_ethiopian_edition(research_session)

    evidence = retrieve_research_evidence(
        research_session,
        'resurrection hope',
        [SourceScope.BIBLICAL_CANON, SourceScope.ETHIOPIAN_TRADITION],
        ResearchDepth.STUDY,
    )

    assert [item.id for item in evidence] == ['scripture:1']
    assert evidence[0].source_type == 'canonical-scripture'


def test_explicit_reference_uses_exact_rows_then_applies_scope(research_session):
    insert_verses(research_session, [
        {'id': 1, 'book': 'Genesis', 'chapter': 1, 'verse': 1, 'text': 'Western exact text', 'translation': 'KJV'},
        {'id': 2, 'book': 'Genesis', 'chapter': 1, 'verse': 1, 'text': 'Ethiopian exact text', 'translation': 'EOTC-COMPOSITE-EN'},
        {'id': 3, 'book': 'Genesis', 'chapter': 1, 'verse': 2, 'text': 'Outside exact range', 'translation': 'KJV'},
    ])
    add_ethiopian_edition(
        research_session,
        work_id='genesis',
        source_language='Hebrew',
        source_tradition='Hebrew Masoretic tradition',
    )

    western = retrieve_research_evidence(
        research_session, 'What does Genesis 1:1 say?',
        [SourceScope.BIBLICAL_CANON], ResearchDepth.SCHOLAR,
    )
    ethiopian = retrieve_research_evidence(
        research_session, 'What does Genesis 1:1 say?',
        [SourceScope.ETHIOPIAN_TRADITION], ResearchDepth.SCHOLAR,
    )

    assert [(item.id, item.reference) for item in western] == [
        ('scripture:1', 'Genesis 1:1')
    ]
    assert [(item.id, item.reference) for item in ethiopian] == [
        ('scripture:2', 'Genesis 1:1')
    ]


@pytest.mark.parametrize('depth, expected', [
    (ResearchDepth.QUICK, 6),
    (ResearchDepth.STUDY, 12),
    (ResearchDepth.DEEP, 24),
    (ResearchDepth.SCHOLAR, 32),
])
def test_depth_controls_result_limit(research_session, depth, expected):
    insert_verses(research_session, [
        {
            'id': index,
            'book': 'Psalms',
            'chapter': 1,
            'verse': index,
            'text': f'wisdom covenant line {index}',
            'translation': 'KJV',
        }
        for index in range(1, 41)
    ])

    evidence = retrieve_research_evidence(
        research_session, 'wisdom covenant', [SourceScope.BIBLICAL_CANON], depth
    )

    assert len(evidence) == expected
    assert [item.id for item in evidence] == [
        f'scripture:{index}' for index in range(1, expected + 1)
    ]


def test_general_question_retrieval_is_bounded_deterministic_and_safe(research_session):
    insert_verses(research_session, [
        {'id': 1, 'book': 'John', 'chapter': 1, 'verse': 1, 'text': "God's faithful covenant", 'translation': 'KJV'},
        {'id': 2, 'book': 'Genesis', 'chapter': 2, 'verse': 1, 'text': 'faithful covenant creation', 'translation': 'KJV'},
        {'id': 3, 'book': 'Romans', 'chapter': 3, 'verse': 1, 'text': 'unrelated teaching', 'translation': 'KJV'},
    ])
    question = "How is God's faithful covenant described? ' OR 1=1 --"

    first = retrieve_research_evidence(
        research_session, question, [SourceScope.BIBLICAL_CANON], ResearchDepth.QUICK
    )
    second = retrieve_research_evidence(
        research_session, question, [SourceScope.BIBLICAL_CANON], ResearchDepth.QUICK
    )

    assert [item.id for item in first] == ['scripture:1', 'scripture:2']
    assert first == second
    assert len(first) <= 6
    assert research_session.scalar(text('SELECT COUNT(*) FROM biblical_texts')) == 3


def test_scope_eligibility_is_applied_before_candidate_limit(research_session):
    insert_verses(research_session, [
        {
            'id': index,
            'book': 'Antiquities',
            'chapter': 1,
            'verse': index,
            'text': 'covenant saturation',
            'translation': 'UNKNOWN',
        }
        for index in range(1, 65)
    ] + [
        {
            'id': 100 + index,
            'book': 'Psalms',
            'chapter': 1,
            'verse': index + 1,
            'text': f'covenant eligible {index}',
            'translation': 'KJV',
        }
        for index in range(6)
    ])

    evidence = retrieve_research_evidence(
        research_session,
        'covenant',
        [SourceScope.BIBLICAL_CANON],
        ResearchDepth.QUICK,
    )

    assert [item.id for item in evidence] == [
        f'scripture:{row_id}' for row_id in range(100, 106)
    ]


def test_missing_optional_metadata_fails_closed_for_nonwestern_scopes():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text('''
            CREATE TABLE biblical_texts (
                id INTEGER PRIMARY KEY, book TEXT, chapter INTEGER,
                verse INTEGER, text TEXT, translation TEXT
            )
        '''))
        connection.execute(text('''
            INSERT INTO biblical_texts VALUES
                (1, 'Genesis', 1, 1, 'creation light', 'KJV'),
                (2, '1 Enoch', 1, 1, 'creation watchers', 'EOTC-COMPOSITE-EN')
        '''))

    with Session(engine) as session:
        assert retrieve_research_evidence(
            session, 'creation', [SourceScope.ETHIOPIAN_TRADITION], ResearchDepth.QUICK
        ) == []
        assert [item.id for item in retrieve_research_evidence(
            session, 'creation', [SourceScope.ALL_SOURCES], ResearchDepth.QUICK
        )] == ['scripture:1']

    engine.dispose()
