import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from patchmind.config import Settings


class PreflightError(RuntimeError):
    """Raised when PatchMind cannot safely start with the configured memory provider."""


def _json_request(
    url: str,
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=body, headers=headers or {}, method="POST" if body else "GET")
    if body:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        raise PreflightError(f"HTTP {error.code} from {url}: {detail}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise PreflightError(f"Cannot reach {url}: {error}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PreflightError(f"Expected a JSON response from {url}") from error


def _origin(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PreflightError(f"Invalid model endpoint URL: {endpoint!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _model_names(payload: Any) -> set[str]:
    items = payload.get("models", []) if isinstance(payload, dict) else []
    names: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in ("name", "model"):
            if item.get(key):
                value = str(item[key])
                names.add(value)
                names.add(value.removesuffix(":latest"))
    return names


def _api_model_names(payload: Any) -> set[str]:
    items = payload.get("data", []) if isinstance(payload, dict) else []
    return {str(item["id"]) for item in items if isinstance(item, dict) and item.get("id")}


def _missing_key(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    return not normalized or normalized.startswith("your-") or normalized in {
        "replace-me",
        "changeme",
        "ollama",
    }


@dataclass
class PreflightChecker:
    settings: Settings

    async def run(self) -> dict[str, Any]:
        if not self.settings.patchmind_preflight:
            return {"status": "skipped", "memory_mode": self.settings.patchmind_memory_mode}
        if self.settings.patchmind_memory_mode == "cloud":
            return await asyncio.to_thread(self._check_cloud)
        return await asyncio.to_thread(self._check_local)

    @property
    def timeout(self) -> float:
        return self.settings.patchmind_preflight_timeout_seconds

    def _check_cloud(self) -> dict[str, Any]:
        url = (self.settings.cognee_service_url or "").rstrip("/")
        if not url:
            raise PreflightError(
                "Cognee Cloud is selected but COGNEE_SERVICE_URL is empty. "
                "Set it to your tenant URL or use PATCHMIND_MEMORY_MODE=local."
            )
        if _missing_key(self.settings.cognee_api_key):
            raise PreflightError(
                "Cognee Cloud is selected but COGNEE_API_KEY is missing or a placeholder."
            )
        headers = {"X-Api-Key": self.settings.cognee_api_key or ""}
        try:
            _json_request(f"{url}/health", timeout=self.timeout, headers=headers)
        except PreflightError as error:
            raise PreflightError(
                f"Cognee Cloud is not healthy at {url}. Check the tenant URL and API key. "
                f"Details: {error}"
            ) from error
        document = _json_request(f"{url}/openapi.json", timeout=self.timeout, headers=headers)
        paths = document.get("paths", {}) if isinstance(document, dict) else {}
        if "/api/v1/improve" not in paths:
            raise PreflightError(
                "Cognee Cloud tenant does not expose POST /api/v1/improve. "
                "PatchMind cannot finalize sessions on this tenant; use local mode or upgrade it."
            )
        return {"status": "ready", "memory_mode": "cloud", "service_url": url}

    def _check_local(self) -> dict[str, Any]:
        if self.settings.llm_provider == "ollama":
            return self._check_ollama()
        return self._check_openai_compatible()

    def _check_ollama(self) -> dict[str, Any]:
        origin = _origin(self.settings.llm_endpoint)
        try:
            tags = _json_request(f"{origin}/api/tags", timeout=self.timeout)
        except PreflightError as error:
            raise PreflightError(
                f"Ollama is not running at {origin}. Start it with 'ollama serve'. Details: {error}"
            ) from error
        installed = _model_names(tags)
        for role, model in (
            ("chat", self.settings.llm_model),
            ("embedding", self.settings.embedding_model),
        ):
            if model not in installed and model.removesuffix(":latest") not in installed:
                raise PreflightError(
                    f"Ollama {role} model '{model}' is not installed. Run: ollama pull {model}"
                )
        embedding = _json_request(
            f"{origin}/api/embed",
            timeout=self.timeout,
            payload={"model": self.settings.embedding_model, "input": "PatchMind preflight"},
        )
        vectors = embedding.get("embeddings", []) if isinstance(embedding, dict) else []
        if not vectors or not isinstance(vectors[0], list):
            raise PreflightError(
                f"Ollama model '{self.settings.embedding_model}' returned no embedding vector."
            )
        actual = len(vectors[0])
        expected = self.settings.embedding_dimensions
        if actual != expected:
            raise PreflightError(
                f"Embedding dimension mismatch for '{self.settings.embedding_model}': "
                f"configured {expected}, model returned {actual}. Set EMBEDDING_DIMENSIONS={actual}."
            )
        return {
            "status": "ready",
            "memory_mode": "local",
            "provider": "ollama",
            "models": [self.settings.llm_model, self.settings.embedding_model],
        }

    def _check_openai_compatible(self) -> dict[str, Any]:
        if _missing_key(self.settings.llm_api_key):
            raise PreflightError(
                f"LLM_API_KEY is missing or a placeholder for provider "
                f"'{self.settings.llm_provider}'."
            )
        if _missing_key(self.settings.embedding_api_key):
            raise PreflightError("EMBEDDING_API_KEY is missing or a placeholder.")
        endpoint = self.settings.llm_endpoint.rstrip("/")
        _origin(endpoint)
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        try:
            models = _json_request(f"{endpoint}/models", timeout=self.timeout, headers=headers)
        except PreflightError as error:
            raise PreflightError(
                f"Cannot authenticate with the OpenAI-compatible API at {endpoint}. "
                f"Check LLM_ENDPOINT and LLM_API_KEY. Details: {error}"
            ) from error
        available = _api_model_names(models)
        requested = self.settings.llm_model.split("/", 1)[-1]
        if available and requested not in available:
            raise PreflightError(
                f"Configured LLM model '{requested}' is not available from {endpoint}."
            )
        embedding_endpoint = self.settings.embedding_endpoint.rstrip("/")
        _origin(embedding_endpoint)
        embedding_headers = {"Authorization": f"Bearer {self.settings.embedding_api_key}"}
        if (
            embedding_endpoint == endpoint
            and self.settings.embedding_api_key == self.settings.llm_api_key
        ):
            embedding_models = available
        else:
            try:
                embedding_payload = _json_request(
                    f"{embedding_endpoint}/models",
                    timeout=self.timeout,
                    headers=embedding_headers,
                )
            except PreflightError as error:
                raise PreflightError(
                    f"Cannot authenticate with the embedding API at {embedding_endpoint}. "
                    f"Check EMBEDDING_ENDPOINT and EMBEDDING_API_KEY. Details: {error}"
                ) from error
            embedding_models = _api_model_names(embedding_payload)
        requested_embedding = self.settings.embedding_model.split("/", 1)[-1]
        if embedding_models and requested_embedding not in embedding_models:
            raise PreflightError(
                f"Configured embedding model '{requested_embedding}' is not available from "
                f"{embedding_endpoint}."
            )
        return {
            "status": "ready",
            "memory_mode": "local",
            "provider": self.settings.llm_provider,
            "model": requested,
            "embedding_model": requested_embedding,
        }
