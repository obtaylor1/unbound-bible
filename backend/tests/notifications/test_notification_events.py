from fastapi.testclient import TestClient
from app.application import create_application
from app.notifications.service import create_notification, update_preferences


def account(client, email, username):
    tokens = client.post('/api/v1/auth/register', json={'email': email, 'username': username, 'password': 'correct-horse-battery-staple'}).json()
    headers = {'Authorization': f"Bearer {tokens['access_token']}"}
    return headers, client.get('/api/v1/auth/me', headers=headers).json()['id']


def test_events_deduplicate_and_read_actions_work(test_settings):
    app = create_application(test_settings)
    with TestClient(app) as client:
        recipient_headers, recipient_id = account(client, 'reader@example.com', 'reader')
        _, actor_id = account(client, 'writer@example.com', 'writer')
        with app.state.session_factory() as session:
            first = create_notification(session, recipient_id=recipient_id, actor_id=actor_id, event_type='reply', target_type='post', target_id='42', message='Writer replied', deduplication_key='reply:42:writer')
            second = create_notification(session, recipient_id=recipient_id, actor_id=actor_id, event_type='reply', target_type='post', target_id='42', message='Writer replied', deduplication_key='reply:42:writer')
            assert first.id == second.id
            for event in ('mention', 'shared_study_activity', 'sermon_complete'):
                create_notification(session, recipient_id=recipient_id, actor_id=actor_id, event_type=event, target_type='test', target_id=event, message=event, deduplication_key=event)
        assert client.get('/api/v1/notifications/unread-count', headers=recipient_headers).json()['count'] == 4
        inbox = client.get('/api/v1/notifications', headers=recipient_headers).json()
        assert len(inbox) == 4
        assert client.patch(f"/api/v1/notifications/{inbox[0]['id']}/read", headers=recipient_headers).status_code == 200
        assert client.post('/api/v1/notifications/read-all', headers=recipient_headers).status_code == 200
        assert client.get('/api/v1/notifications/unread-count', headers=recipient_headers).json()['count'] == 0


def test_preferences_suppress_selected_events(test_settings):
    app = create_application(test_settings)
    with TestClient(app) as client:
        headers, recipient_id = account(client, 'reader@example.com', 'reader')
        with app.state.session_factory() as session:
            update_preferences(session, recipient_id, ['mention'])
            assert create_notification(session, recipient_id=recipient_id, event_type='mention', target_type='post', target_id='1', message='hidden', deduplication_key='hidden') is None
            assert create_notification(session, recipient_id=recipient_id, event_type='reply', target_type='post', target_id='2', message='visible', deduplication_key='visible') is not None
        assert client.get('/api/v1/notifications/unread-count', headers=headers).json()['count'] == 1
