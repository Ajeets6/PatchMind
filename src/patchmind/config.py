from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    patchmind_memory_mode: Literal["local", "cloud"] = "local"
    patchmind_preflight: bool = True
    patchmind_preflight_timeout_seconds: float = 10.0
    cognee_service_url: str | None = None
    cognee_api_key: str | None = None
    patchmind_cognee_data_dir: Path = Path(".patchmind/cognee/data")
    patchmind_cognee_system_dir: Path = Path(".patchmind/cognee/system")

    # Cognee consumes these standard OpenAI-compatible provider settings.
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5-coder:7b"
    llm_endpoint: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_max_completion_tokens: int = 4096
    embedding_provider: str = "openai_compatible"
    embedding_model: str = "nomic-embed-text"
    embedding_endpoint: str = "http://localhost:11434/v1"
    embedding_api_key: str = "ollama"
    embedding_dimensions: int = 768
    patchmind_max_file_bytes: int = 100_000
    patchmind_max_commits: int = 50
    patchmind_max_diff_chars: int = 4_000
    patchmind_transport: Literal["stdio", "streamable-http"] = "streamable-http"
    patchmind_host: str = "0.0.0.0"
    patchmind_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
