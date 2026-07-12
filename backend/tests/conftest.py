import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture
def test_settings(tmp_path):
    from app.config import Settings

    return Settings(
        environment='test',
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        jwt_secret_key='test-secret-key-that-is-at-least-32-characters',
        public_base_url='http://localhost:5001',
        cors_origins=['http://localhost:5001'],
        ai_chat_provider='demo',
        ai_embedding_provider='demo',
        ai_transcription_provider='demo',
    )
