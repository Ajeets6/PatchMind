import re
from collections import defaultdict


class InMemoryMemoryStore:
    """Deterministic test/demo store with the same lifecycle as Cognee."""

    def __init__(self) -> None:
        self.datasets: dict[str, list[str]] = defaultdict(list)
        self.sessions: dict[tuple[str, str], list[str]] = defaultdict(list)

    async def preflight(self):
        return {"status": "ready", "memory_mode": "in_memory"}

    async def remember(
        self, records, dataset, *, session_id=None, custom_prompt=None, background=False
    ):
        target = self.sessions[(dataset, session_id)] if session_id else self.datasets[dataset]
        target.extend(record for record in records if record not in target)

    async def recall(self, query, dataset, *, top_k=10):
        terms = set(re.findall(r"[a-z0-9_./-]+", query.lower()))

        def score(record: str) -> int:
            words = set(re.findall(r"[a-z0-9_./-]+", record.lower()))
            return len(terms & words)

        ranked = sorted(self.datasets[dataset], key=score, reverse=True)
        return [item for item in ranked if score(item) > 0][:top_k]

    async def improve(self, dataset, session_ids, *, background=False):
        for session_id in session_ids:
            await self.remember(self.sessions.pop((dataset, session_id), []), dataset)

    async def forget(self, dataset):
        self.datasets.pop(dataset, None)
        for key in [key for key in self.sessions if key[0] == dataset]:
            self.sessions.pop(key)
