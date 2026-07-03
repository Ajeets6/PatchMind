from functools import lru_cache

import structlog
from mcp.server.fastmcp import FastMCP

from patchmind.config import get_settings
from patchmind.memory.cognee_store import CogneeMemoryStore
from patchmind.service import PatchMindService

INSTRUCTIONS = (
    "PatchMind provides persistent repository memory. Before changing unfamiliar or "
    "historically sensitive code, call patchmind_get_context. After testing an approach, "
    "call patchmind_record_outcome. Finalize validated sessions with patchmind_finalize_session."
)
settings = get_settings()
mcp = FastMCP(
    "PatchMind", instructions=INSTRUCTIONS, host=settings.patchmind_host, port=settings.patchmind_port
)


@lru_cache
def get_service() -> PatchMindService:
    return PatchMindService(CogneeMemoryStore(settings), settings)


@mcp.tool()
async def patchmind_index_repository(
    repository_path: str, max_commits: int = 50, include_source: bool = True
) -> dict:
    """Index repository files, commits, changes and test relationships."""
    return await get_service().index_repository(repository_path, max_commits, include_source)


@mcp.tool()
async def patchmind_get_context(
    repository_path: str,
    task: str,
    file_paths: list[str] | None = None,
    symbol: str | None = None,
    top_k: int = 10,
) -> dict:
    """Retrieve repository decisions, previous attempts and relevant evidence."""
    return await get_service().get_context(repository_path, task, file_paths, symbol, top_k)


@mcp.tool()
async def patchmind_find_previous_attempts(
    repository_path: str, problem: str, file_path: str | None = None
) -> dict:
    """Find previous successful, failed, rejected or reverted approaches."""
    return await get_service().find_previous_attempts(repository_path, problem, file_path)


@mcp.tool()
async def patchmind_record_outcome(
    repository_path: str,
    session_id: str,
    task: str,
    approach: str,
    outcome: str,
    evidence: str,
    affected_files: list[str],
    tests: list[str] | None = None,
) -> dict:
    """Record a coding attempt and its observed outcome in session memory."""
    return await get_service().record_outcome(
        repository_path, session_id, task, approach, outcome, evidence, affected_files, tests
    )


@mcp.tool()
async def patchmind_finalize_session(
    repository_path: str, session_id: str, summary: str
) -> dict:
    """Enrich the graph and promote useful session memory to permanent memory."""
    return await get_service().finalize_session(repository_path, session_id, summary)


def main() -> None:
    structlog.configure(processors=[structlog.processors.JSONRenderer()])
    get_service()  # Fail fast on memory/provider configuration before accepting MCP calls.
    mcp.run(transport=settings.patchmind_transport)


if __name__ == "__main__":
    main()
