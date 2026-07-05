import inspect
import json
import os
import warnings
from pathlib import Path
from typing import Any

import structlog

from patchmind.config import Settings
from patchmind.memory.preflight import PreflightChecker

log = structlog.get_logger()


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [json.dumps(value, default=str)]
    if isinstance(value, (list, tuple)):
        result: list[str] = []
        for item in value:
            result.extend(_strings(item))
        return result
    return [str(value)]


async def _await(value):
    return await value if inspect.isawaitable(value) else value


class CogneeMemoryStore:
    """Thin adapter around Cognee, isolated for SDK and cloud portability."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        if self.settings.patchmind_memory_mode == "cloud":
            if not self.settings.cognee_service_url:
                raise ValueError("COGNEE_SERVICE_URL is required in cloud memory mode")
            message = (
                "PatchMind cloud memory mode requires the tenant to expose "
                "POST /api/v1/improve; session finalization fails when it is unavailable."
            )
            warnings.warn(message, RuntimeWarning, stacklevel=2)
            log.warning("cloud_memory_mode", requirement="POST /api/v1/improve")
        else:
            self._configure_local()
            if self.settings.cognee_service_url:
                message = (
                    "COGNEE_SERVICE_URL is configured but ignored because "
                    "PATCHMIND_MEMORY_MODE=local. Set it to cloud explicitly to use the tenant."
                )
                warnings.warn(message, RuntimeWarning, stacklevel=2)
                log.warning("cloud_configuration_ignored")
        import cognee

        self.client = cognee
        self._connected = False

    async def preflight(self) -> dict[str, Any]:
        result = await PreflightChecker(self.settings).run()
        log.info("memory_preflight", **result)
        return result

    def _configure_local(self) -> None:
        data_dir = Path(self.settings.patchmind_cognee_data_dir).resolve()
        system_dir = Path(self.settings.patchmind_cognee_system_dir).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        system_dir.mkdir(parents=True, exist_ok=True)
        values = {
            "DATA_ROOT_DIRECTORY": str(data_dir),
            "SYSTEM_ROOT_DIRECTORY": str(system_dir),
            "CACHE_ROOT_DIRECTORY": str(system_dir / "cache"),
            "CACHING": "true",
            "ENABLE_BACKEND_ACCESS_CONTROL": "false",
            "COGNEE_SKIP_CONNECTION_TEST": "true",
            "LLM_PROVIDER": self.settings.llm_provider,
            "LLM_MODEL": self.settings.llm_model,
            "LLM_ENDPOINT": self.settings.llm_endpoint,
            "LLM_API_KEY": self.settings.llm_api_key,
            "LLM_MAX_COMPLETION_TOKENS": str(self.settings.llm_max_completion_tokens),
            "EMBEDDING_PROVIDER": self.settings.embedding_provider,
            "EMBEDDING_MODEL": self.settings.embedding_model,
            "EMBEDDING_ENDPOINT": self.settings.embedding_endpoint,
            "EMBEDDING_API_KEY": self.settings.embedding_api_key,
            "EMBEDDING_DIMENSIONS": str(self.settings.embedding_dimensions),
        }
        os.environ.update(values)

    async def _connect(self) -> None:
        if self._connected:
            return
        if self.settings.patchmind_memory_mode == "cloud":
            await self.client.serve(
                url=self.settings.cognee_service_url,
                api_key=self.settings.cognee_api_key or "",
            )
        self._connected = True

    async def remember(
        self, records, dataset, *, session_id=None, custom_prompt=None, background=False
    ):
        await self._connect()
        kwargs: dict[str, Any] = {"dataset_name": dataset}
        if session_id:
            kwargs["session_id"] = session_id
            kwargs["self_improvement"] = False
        if custom_prompt:
            kwargs["custom_prompt"] = custom_prompt
        if background:
            kwargs["run_in_background"] = True
        await _await(self.client.remember(records, **kwargs))

    async def recall(self, query, dataset, *, top_k=10):
        await self._connect()
        kwargs: dict[str, Any] = {"datasets": [dataset], "top_k": top_k}
        if self.settings.patchmind_recall_mode == "chunks":
            kwargs.update(
                query_type=self.client.SearchType.CHUNKS,
                auto_route=False,
                only_context=True,
            )
        result = await _await(self.client.recall(query, **kwargs))
        return _strings(result)

    async def improve(self, dataset, session_ids, *, background=False):
        await self._connect()
        await _await(
            self.client.improve(
                dataset=dataset,
                session_ids=session_ids,
                run_in_background=background,
            )
        )

    async def forget(self, dataset):
        await self._connect()
        forget = getattr(self.client, "forget", None)
        if forget:
            await _await(forget(dataset=dataset))
            return
        prune = getattr(self.client, "prune", None)
        if prune:
            await _await(prune(dataset_name=dataset))
            return
        raise RuntimeError("Installed Cognee SDK exposes neither forget() nor prune()")
