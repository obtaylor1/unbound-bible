from fastapi.testclient import TestClient
from sqlalchemy import text
from app.application import create_application


def account(client, email, username):
    data = client.post('/api/v1/auth/register', json={'email': email, 'username': username, 'password': 'correct-horse-battery-staple'}).json()
    return {'Authorization': f"Bearer {data['access_token']}"}


def test_search_groups_public_content_and_only_current_users_private_records(test_settings):
    app = create_application(test_settings)
    with app.state.database_engine.begin() as connection:
        connection.execute(text('CREATE TABLE biblical_texts (id INTEGER PRIMARY KEY, book TEXT, chapter INTEGER, verse INTEGER, text TEXT, translation TEXT)'))
        connection.execute(text("INSERT INTO biblical_texts VALUES (1, 'Romans', 8, 1, 'There is therefore now no condemnation', 'KJV')"))
    with TestClient(app) as client:
        owner = account(client, 'owner@example.com', 'owner'); other = account(client, 'other@example.com', 'other')
        client.post('/api/v1/notes', headers=owner, json={'passage_reference': 'Romans 8:1', 'content': 'private condemnation note'})
        client.post('/api/v1/notes', headers=other, json={'passage_reference': 'Romans 8:1', 'content': 'other secret condemnation note'})

        anonymous = client.get('/api/v1/search?q=condemnation').json()
        assert any(item['group'] == 'scripture' for item in anonymous['results'])
        assert not any(item['group'] == 'my_notes' for item in anonymous['results'])

        mine = client.get('/api/v1/search?q=condemnation', headers=owner).json()['results']
        private = [item for item in mine if item['group'] == 'my_notes']
        assert len(private) == 1
        assert private[0]['title'] == 'Romans 8:1'
        assert all('other secret' not in item.get('excerpt', '') for item in mine)


def test_search_is_bounded_and_requires_a_meaningful_query(test_settings):
    with TestClient(create_application(test_settings)) as client:
        assert client.get('/api/v1/search?q=a').status_code == 422
        data = client.get('/api/v1/search?q=anything&limit=200').json()
        assert data['limit'] <= 50
