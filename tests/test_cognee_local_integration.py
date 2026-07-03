import os
from uuid import uuid4

import pytest

from patchmind.config import Settings
from patchmind.memory.cognee_store import CogneeMemoryStore


pytestmark = pytest.mark.skipif(
    os.getenv("PATCHMIND_RUN_COGNEE_LOCAL_INTEGRATION") != "1",
    reason="Set PATCHMIND_RUN_COGNEE_LOCAL_INTEGRATION=1 with Ollama running",
)


async def test_local_cognee_session_promotion(tmp_path):
    store = CogneeMemoryStore(
        Settings(
            patchmind_memory_mode="local",
            cognee_service_url=None,
            patchmind_cognee_data_dir=tmp_path / "data",
            patchmind_cognee_system_dir=tmp_path / "system",
        )
    )
    dataset = f"patchmind_local_integration_{uuid4().hex}"
    session_id = f"local-{uuid4().hex}"
    created = False

    try:
        # Normal PatchMind usage creates the permanent repository dataset during indexing.
        await store.remember(
            ["REPOSITORY\nName: patchmind-local-integration\nStatus: indexed"],
            dataset,
        )
        created = True
        await store.remember(
            ["PATCH ATTEMPT\nApproach: use an amber lock\nOutcome: failed"],
            dataset,
            session_id=session_id,
        )
        await store.improve(dataset, [session_id])
        result = await store.recall("amber lock failed", dataset, top_k=5)
        assert result
    finally:
        if created:
            await store.forget(dataset)
