from typing import Protocol


class MemoryStore(Protocol):
    async def preflight(self) -> dict: ...

    async def remember(
        self,
        records: list[str],
        dataset: str,
        *,
        session_id: str | None = None,
        custom_prompt: str | None = None,
    ) -> None: ...

    async def recall(self, query: str, dataset: str, *, top_k: int = 10) -> list[str]: ...

    async def improve(self, dataset: str, session_ids: list[str]) -> None: ...

    async def forget(self, dataset: str) -> None: ...
