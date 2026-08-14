import httpx
import pytest

from app.ai.contracts import ChatMessage, ProviderError
from app.ai.factory import create_chat_provider


def transport(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/chat/completions"):
        return httpx.Response(200, json={"model": "test-openai", "choices": [{"message": {"content": "A grounded response"}}]})
    if request.url.path.endswith("/api/chat"):
        return httpx.Response(200, json={"model": "test-ollama", "message": {"content": "A local response"}})
    return httpx.Response(404)


@pytest.mark.parametrize("provider_name", ["openai_compatible", "ollama", "demo"])
@pytest.mark.asyncio
async def test_chat_providers_return_normalized_metadata(provider_name, test_settings):
    client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    provider = create_chat_provider(provider_name, test_settings, http_client=client)
    result = await provider.complete([ChatMessage(role="user", content="Question")])
    await client.aclose()
    assert result.provider == provider_name
    assert result.model
    assert result.content
    assert result.is_demo is (provider_name == "demo")


def test_unknown_provider_fails_closed(test_settings):
    with pytest.raises(ValueError, match="Unsupported chat provider"):
        create_chat_provider("mystery", test_settings)


@pytest.mark.parametrize('provider_name', ['openai_compatible', 'ollama'])
@pytest.mark.parametrize('error_type', [httpx.ConnectError, httpx.ReadError])
@pytest.mark.asyncio
async def test_chat_provider_maps_network_errors_to_retryable_unavailable(
    provider_name, error_type, test_settings,
):
    def fail(request: httpx.Request) -> httpx.Response:
        raise error_type('private network detail', request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    provider = create_chat_provider(provider_name, test_settings, http_client=client)

    with pytest.raises(ProviderError) as raised:
        await provider.complete([ChatMessage(role='user', content='Question')])

    await client.aclose()
    assert raised.value.code == 'unavailable'
    assert raised.value.retryable is True
    assert 'private network detail' not in str(raised.value)
