import logging
import io
import wave
from pathlib import Path
from fastapi.testclient import TestClient
from app.application import create_application
from app.observability.logging import RedactingFilter


def register(client):
    data = client.post('/api/v1/auth/register', json={'email': 'reader@example.com', 'username': 'reader', 'password': 'correct-horse-battery-staple'}).json()
    return {'Authorization': f"Bearer {data['access_token']}"}


def test_login_and_ai_rate_limits(test_settings):
    test_settings.auth_rate_limit = 2; test_settings.ai_rate_limit = 2
    app = create_application(test_settings)
    with TestClient(app) as client:
        register(client)
        payload = {'email': 'reader@example.com', 'password': 'wrong-password'}
        assert client.post('/api/v1/auth/login', json=payload).status_code == 401
        assert client.post('/api/v1/auth/login', json=payload).status_code == 401
        limited = client.post('/api/v1/auth/login', json=payload)
        assert limited.status_code == 429 and limited.json()['detail']['code'] == 'rate_limited'
        assert client.post('/api/v1/chat/ask', json={'question': 'Genesis 1:1'}).status_code == 200
        assert client.post('/api/v1/chat/ask', json={'question': 'Genesis 1:1'}).status_code == 200
        assert client.post('/api/v1/chat/ask', json={'question': 'Genesis 1:1'}).status_code == 429


def test_audio_upload_rejects_invalid_and_oversized_files_and_cleans_up(test_settings, tmp_path):
    test_settings.upload_max_bytes = 8
    test_settings.upload_temp_dir = str(tmp_path)
    with TestClient(create_application(test_settings)) as client:
        headers = register(client)
        invalid = client.post('/api/v1/analyze/sermon', headers=headers, files={'file': ('notes.txt', b'hello', 'text/plain')})
        assert invalid.status_code == 415
        oversized = client.post('/api/v1/analyze/sermon', headers=headers, files={'file': ('sermon.mp3', b'123456789', 'audio/mpeg')})
        assert oversized.status_code == 413
        test_settings.upload_max_bytes = 1024
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(1); audio.setframerate(8000); audio.writeframes(b'\x80' * 80)
        valid = client.post('/api/v1/analyze/sermon', headers=headers, files={'file': ('sermon.wav', buffer.getvalue(), 'audio/wav')})
        assert valid.status_code == 200
    assert list(Path(tmp_path).glob('unbound-sermon-*')) == []


def test_logging_redacts_tokens_secrets_and_private_content():
    record = logging.LogRecord('test', logging.INFO, __file__, 1, 'Authorization=Bearer abc JWT_SECRET_KEY=secret content=private-study', (), None)
    assert RedactingFilter().filter(record)
    message = record.getMessage()
    assert 'abc' not in message and 'secret' not in message and 'private-study' not in message
    assert '[REDACTED]' in message
