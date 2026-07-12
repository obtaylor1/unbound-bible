from sqlalchemy import text
from fastapi.testclient import TestClient

from app.application import create_application


def seed_scripture(app):
    with app.state.database_engine.begin() as connection:
        connection.execute(text("CREATE TABLE biblical_texts (id INTEGER PRIMARY KEY, book TEXT, chapter INTEGER, verse INTEGER, text TEXT, translation TEXT)"))
        connection.execute(text("INSERT INTO biblical_texts (book, chapter, verse, text, translation) VALUES ('Genesis', 1, 1, 'In the beginning God created the heaven and the earth.', 'KJV'), ('John', 1, 1, 'In the beginning was the Word.', 'KJV')"))


def test_exact_reference_answer_has_only_verified_citations(test_settings):
    app = create_application(test_settings); seed_scripture(app)
    with TestClient(app) as client:
        response = client.post('/api/v1/chat/ask', json={'question': 'What does Genesis 1:1 say?'})
    assert response.status_code == 200
    data = response.json()
    assert data['grounding_status'] == 'grounded'
    assert data['sources']
    assert all(source['reference'] == 'Genesis 1:1' for source in data['sources'])
    assert set(data['citation_ids']) == {source['id'] for source in data['sources']}


def test_missing_evidence_is_insufficient_and_has_no_fake_citations(test_settings):
    app = create_application(test_settings); seed_scripture(app)
    with TestClient(app) as client:
        response = client.post('/api/v1/chat/ask', json={'question': 'What does Tobit 99:4 say?'})
    assert response.status_code == 200
    data = response.json()
    assert data['grounding_status'] == 'insufficient'
    assert data['sources'] == []
    assert data['citation_ids'] == []
