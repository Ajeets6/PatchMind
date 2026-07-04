import pytest

from patchmind.config import Settings
from patchmind.memory.preflight import PreflightChecker, PreflightError


def local_settings(**overrides):
    values = {
        "patchmind_memory_mode": "local",
        "cognee_service_url": None,
        "llm_provider": "ollama",
        "llm_model": "qwen2.5-coder:7b",
        "llm_endpoint": "http://localhost:11434/v1",
        "embedding_model": "nomic-embed-text",
        "embedding_dimensions": 3,
    }
    values.update(overrides)
    return Settings(**values)


async def test_ollama_not_running_has_start_command(monkeypatch):
    def unavailable(*args, **kwargs):
        raise PreflightError("connection refused")

    monkeypatch.setattr("patchmind.memory.preflight._json_request", unavailable)
    with pytest.raises(PreflightError, match="ollama serve"):
        await PreflightChecker(local_settings()).run()


async def test_missing_ollama_model_has_pull_command(monkeypatch):
    monkeypatch.setattr(
        "patchmind.memory.preflight._json_request",
        lambda *args, **kwargs: {"models": [{"name": "nomic-embed-text:latest"}]},
    )
    with pytest.raises(PreflightError, match=r"ollama pull qwen2.5-coder:7b"):
        await PreflightChecker(local_settings()).run()


async def test_embedding_dimension_mismatch_reports_value(monkeypatch):
    def response(url, **kwargs):
        if url.endswith("/api/tags"):
            return {
                "models": [
                    {"name": "qwen2.5-coder:7b"},
                    {"name": "nomic-embed-text:latest"},
                ]
            }
        return {"embeddings": [[0.1, 0.2, 0.3, 0.4]]}

    monkeypatch.setattr("patchmind.memory.preflight._json_request", response)
    with pytest.raises(PreflightError, match="EMBEDDING_DIMENSIONS=4"):
        await PreflightChecker(local_settings()).run()


async def test_ollama_preflight_succeeds(monkeypatch):
    def response(url, **kwargs):
        if url.endswith("/api/tags"):
            return {
                "models": [
                    {"name": "qwen2.5-coder:7b"},
                    {"name": "nomic-embed-text:latest"},
                ]
            }
        return {"embeddings": [[0.1, 0.2, 0.3]]}

    monkeypatch.setattr("patchmind.memory.preflight._json_request", response)
    result = await PreflightChecker(local_settings()).run()
    assert result["status"] == "ready"
    assert result["provider"] == "ollama"


async def test_openai_placeholder_key_is_rejected():
    settings = local_settings(
        llm_provider="openai",
        llm_api_key="your-openai-api-key",
        embedding_api_key="your-openai-api-key",
    )
    with pytest.raises(PreflightError, match="LLM_API_KEY"):
        await PreflightChecker(settings).run()


async def test_missing_hosted_embedding_model_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "patchmind.memory.preflight._json_request",
        lambda *args, **kwargs: {"data": [{"id": "gpt-4.1-mini"}]},
    )
    settings = local_settings(
        llm_provider="openai",
        llm_model="openai/gpt-4.1-mini",
        llm_api_key="valid-key",
        llm_endpoint="https://api.example/v1",
        embedding_provider="openai",
        embedding_model="openai/text-embedding-3-small",
        embedding_endpoint="https://api.example/v1",
        embedding_api_key="valid-key",
    )
    with pytest.raises(PreflightError, match="Configured embedding model"):
        await PreflightChecker(settings).run()


async def test_cloud_requires_api_key():
    settings = Settings(
        patchmind_memory_mode="cloud",
        cognee_service_url="https://tenant.example",
        cognee_api_key="your-cognee-key",
    )
    with pytest.raises(PreflightError, match="COGNEE_API_KEY"):
        await PreflightChecker(settings).run()


async def test_cloud_requires_improve_route(monkeypatch):
    def response(url, **kwargs):
        return {"status": "ok"} if url.endswith("/health") else {"paths": {}}

    monkeypatch.setattr("patchmind.memory.preflight._json_request", response)
    settings = Settings(
        patchmind_memory_mode="cloud",
        cognee_service_url="https://tenant.example",
        cognee_api_key="valid-secret",
    )
    with pytest.raises(PreflightError, match="does not expose POST /api/v1/improve"):
        await PreflightChecker(settings).run()
