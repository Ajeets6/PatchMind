import pytest

from patchmind.config import Settings
from patchmind.memory.in_memory import InMemoryMemoryStore
from patchmind.service import PatchMindService


@pytest.fixture
def service():
    return PatchMindService(InMemoryMemoryStore(), Settings(patchmind_max_commits=10))


async def test_index_and_retrieve_repository_context(service, demo_repository):
    result = await service.index_repository(str(demo_repository))
    assert result["status"] == "ready"
    assert result["files_indexed"] == 4
    assert result["commits_indexed"] == 1
    context = await service.get_context(str(demo_repository), "Why use process-level lock?")
    assert context["status"] == "found"
    assert any("Per-request locks failed" in item for item in context["context"])


async def test_index_deduplicates_unchanged_records(service, demo_repository):
    first = await service.index_repository(str(demo_repository))
    second = await service.index_repository(str(demo_repository))
    assert first["records_uploaded"] > 0
    assert second["records_uploaded"] == 0


async def test_failed_attempt_survives_new_session(service, demo_repository):
    await service.record_outcome(
        str(demo_repository), "session-a", "Fix concurrent session corruption",
        "Use one lock per request", "failed", "Different workers used different locks",
        ["src/session_store.py"], ["test_concurrent_sessions"],
    )
    before = await service.get_context(str(demo_repository), "one lock per request")
    assert before["status"] == "not_found"
    await service.finalize_session(str(demo_repository), "session-a", "Validated failed approach")
    after = await service.get_context(str(demo_repository), "Fix concurrent session corruption")
    text = "\n".join(after["context"])
    assert "one lock per request" in text
    assert "failed" in text


async def test_attempts_have_stable_groups(service, demo_repository):
    await service.record_outcome(
        str(demo_repository), "s", "corruption", "per-request locks", "rejected",
        "review feedback", ["src/session_store.py"],
    )
    await service.finalize_session(str(demo_repository), "s", "done")
    result = await service.find_previous_attempts(str(demo_repository), "corruption")
    assert set(result) == {"failed", "rejected", "reverted", "successful", "unknown"}
    assert result["rejected"]


async def test_invalid_outcome_is_rejected(service, demo_repository):
    with pytest.raises(ValueError):
        await service.record_outcome(
            str(demo_repository), "s", "task", "approach", "maybe", "none", []
        )
