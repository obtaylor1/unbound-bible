import pytest
from pydantic import ValidationError
from app.config import Settings


BASE = {'environment': 'production', 'database_url': 'postgresql://user:pass@db/unbound', 'jwt_secret_key': 'a-secure-production-secret-with-32-chars', 'public_base_url': 'https://bible.example', 'cors_origins': ['https://bible.example'], 'ai_chat_provider': 'openai_compatible', 'ai_embedding_provider': 'openai_compatible', 'ai_transcription_provider': 'openai_compatible', 'ai_api_key': 'provider-key'}


@pytest.mark.parametrize('changes', [
    {'jwt_secret_key': 'short'}, {'cors_origins': ['*']}, {'database_url': ''},
    {'ai_chat_provider': 'demo'}, {'ai_embedding_provider': 'demo'}, {'ai_transcription_provider': 'demo'},
])
def test_production_fails_closed(changes):
    with pytest.raises(ValidationError): Settings(**(BASE | changes))


def test_production_demo_requires_explicit_override():
    settings = Settings(**(BASE | {'ai_chat_provider': 'demo', 'allow_production_demo': True}))
    assert settings.allow_production_demo is True
