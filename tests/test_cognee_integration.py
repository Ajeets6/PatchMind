import os
from uuid import uuid4

import pytest

from patchmind.config import Settings
from patchmind.memory.cognee_store import CogneeMemoryStore


pytestmark = pytest.mark.skipif(
    os.getenv("PATCHMIND_RUN_COGNEE_CLOUD_INTEGRATION") != "1",
    reason="Set PATCHMIND_RUN_COGNEE_CLOUD_INTEGRATION=1 to exercise Cognee Cloud",
)


async def test_live_cognee_memory_lifecycle():
    settings = Settings(patchmind_memory_mode="cloud")
    if not settings.cognee_service_url or not settings.cognee_api_key:
        pytest.skip("Cognee Cloud credentials are not configured")

    store = CogneeMemoryStore(settings)
    dataset = f"patchmind_integration_{uuid4().hex}"
    session_id = f"integration-{uuid4().hex}"

    try:
        await store.remember(
            [
                "ENGINEERING DECISION\n\n"
                "Repository: patchmind-integration\n"
                "Decision: Preserve the cobalt mutex around session writes\n"
                "Status: accepted\n"
                "Reason: Concurrent workers otherwise truncate session data."
            ],
            dataset,
        )
        permanent = await store.recall("Why preserve the cobalt mutex?", dataset, top_k=5)
        assert permanent

        await store.remember(
            [
                "PATCH ATTEMPT\n\n"
                "Repository: patchmind-integration\n"
                "Task: Protect session writes\n"
                "Approach: Replace the cobalt mutex with per-request locks\n"
                "Outcome: failed\n"
                "Evidence: Concurrent workers held distinct locks."
            ],
            dataset,
            session_id=session_id,
        )
        await store.improve(dataset, [session_id])
        promoted = await store.recall("per-request locks cobalt mutex", dataset, top_k=5)
        assert promoted
    finally:
        await store.forget(dataset)
