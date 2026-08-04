from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.database import Base, create_database_engine, create_session_factory
from app.library.seed import seed_ethiopian_canon


@pytest.fixture
def commentary_session(test_settings) -> Generator[Session, None, None]:
    # Importing the models registers the commentary tables before metadata creation.
    from app.commentary import models as commentary_models  # noqa: F401

    engine = create_database_engine(test_settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_ethiopian_canon(session)
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def genesis() -> str:
    return 'genesis'


@pytest.fixture
def make_commentary_source(commentary_session):
    from app.commentary.models import CommentarySource

    def make(source_id: str = 'test-commentary', **overrides) -> CommentarySource:
        values = {
            'id': source_id,
            'title': 'Test Commentary',
            'abbreviation': 'TC',
            'author': 'Test Author',
            'publication_period': '2026',
            'tradition': 'Ethiopian Orthodox',
            'license_spdx': 'CC-BY-4.0',
            'license_url': 'https://creativecommons.org/licenses/by/4.0/',
            'attribution': 'Test attribution',
            'provenance_url': 'https://example.test/commentary',
        }
        values.update(overrides)
        source = CommentarySource(**values)
        commentary_session.add(source)
        commentary_session.flush()
        return source

    return make


@pytest.fixture
def commentary_source(make_commentary_source):
    return make_commentary_source()


@pytest.fixture
def make_commentary_edition(commentary_session, commentary_source):
    from app.commentary.models import CommentaryEdition

    def make(dataset_version: str = '1.0.0', **overrides) -> CommentaryEdition:
        values = {
            'id': uuid4(),
            'source_id': commentary_source.id,
            'dataset_version': dataset_version,
            'source_checksum': 'a' * 64,
            'status': 'verified',
            'coverage': {},
        }
        values.update(overrides)
        edition = CommentaryEdition(**values)
        commentary_session.add(edition)
        commentary_session.flush()
        return edition

    return make


@pytest.fixture
def commentary_editions(make_commentary_edition):
    return (make_commentary_edition('1.0.0'), make_commentary_edition('2.0.0'))


@pytest.fixture
def published_edition(make_commentary_edition):
    return make_commentary_edition('published-1.0.0', status='published')
