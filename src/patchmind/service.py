import re
from patchmind.config import Settings
from patchmind.memory.base import MemoryStore
from patchmind.models import Outcome
from patchmind.prompts import EXTRACTION_PROMPT
from patchmind.repository.formatter import format_attempt, format_commit, format_file
from patchmind.repository.git_history import read_recent_commits
from patchmind.repository.index_state import IndexState
from patchmind.repository.scanner import read_source_files, scan_repository


class PatchMindService:
    def __init__(self, memory: MemoryStore, settings: Settings | None = None) -> None:
        self.memory = memory
        self.settings = settings or Settings()

    async def index_repository(self, repository_path, max_commits=50, include_source=True):
        repo = scan_repository(repository_path)
        limit = min(max(0, max_commits), self.settings.patchmind_max_commits)
        files = read_source_files(repo.root, self.settings.patchmind_max_file_bytes) if include_source else []
        commits = read_recent_commits(repo.root, limit, self.settings.patchmind_max_diff_chars)
        state = IndexState(repo.root)
        pending: list[tuple[str, str]] = []
        for source in files:
            key = f"file:{source.path}:{source.content_hash}"
            if state.unseen(key):
                pending.append((key, format_file(repo.name, repo.branch, source)))
        for commit in commits:
            key = f"commit:{commit.hash}"
            if state.unseen(key):
                pending.append((key, format_commit(repo.name, commit)))
        if pending:
            await self.memory.remember(
                [record for _, record in pending], repo.dataset, custom_prompt=EXTRACTION_PROMPT
            )
            for key, _ in pending:
                state.add(key)
            state.save()
        return {
            "repository_id": repo.repository_id,
            "dataset": repo.dataset,
            "files_indexed": len(files),
            "test_files_indexed": sum(file.is_test for file in files),
            "commits_indexed": len(commits),
            "records_uploaded": len(pending),
            "status": "ready",
        }

    async def get_context(self, repository_path, task, file_paths=None, symbol=None, top_k=10):
        repo = scan_repository(repository_path)
        qualifiers = [task]
        if file_paths:
            qualifiers.append("Files: " + ", ".join(file_paths))
        if symbol:
            qualifiers.append("Symbol: " + symbol)
        query = "\n".join(qualifiers)
        records = await self.memory.recall(query, repo.dataset, top_k=max(1, min(top_k, 50)))
        return {
            "repository_id": repo.repository_id,
            "task": task,
            "context": records,
            "evidence_count": len(records),
            "status": "found" if records else "not_found",
        }

    async def find_previous_attempts(self, repository_path, problem, file_path=None):
        repo = scan_repository(repository_path)
        query = f"Previous attempts for: {problem}"
        if file_path:
            query += f"\nFile: {file_path}"
        records = await self.memory.recall(query, repo.dataset, top_k=30)
        grouped = {name: [] for name in ("failed", "rejected", "reverted", "successful", "unknown")}
        for record in records:
            match = re.search(
                r"(?:Outcome|Status):\s*(successful|failed|rejected|reverted|inconclusive)",
                record,
                re.IGNORECASE,
            )
            category = match.group(1).lower() if match else "unknown"
            if category == "inconclusive":
                category = "unknown"
            grouped[category].append(record)
        return grouped

    async def record_outcome(
        self, repository_path, session_id, task, approach, outcome, evidence,
        affected_files, tests=None,
    ):
        repo = scan_repository(repository_path)
        normalized = Outcome(outcome).value
        record = format_attempt(
            repo.name, task, approach, normalized, evidence, affected_files, tests
        )
        await self.memory.remember([record], repo.dataset, session_id=session_id)
        return {
            "repository_id": repo.repository_id,
            "dataset": repo.dataset,
            "session_id": session_id,
            "outcome": normalized,
            "status": "recorded",
        }

    async def finalize_session(self, repository_path, session_id, summary):
        repo = scan_repository(repository_path)
        summary_record = f"""SESSION SUMMARY

Repository: {repo.name}
Session: {session_id}
Summary: {summary}
Status: validated and finalized
"""
        await self.memory.remember([summary_record], repo.dataset, session_id=session_id)
        await self.memory.improve(repo.dataset, [session_id])
        return {
            "repository_id": repo.repository_id,
            "dataset": repo.dataset,
            "session_id": session_id,
            "status": "finalized",
            "memory_mode": self.settings.patchmind_memory_mode,
            "promotion_strategy": "cognee_improve",
        }

    async def forget_repository(self, repository_path):
        repo = scan_repository(repository_path)
        await self.memory.forget(repo.dataset)
        return {"repository_id": repo.repository_id, "dataset": repo.dataset, "status": "forgotten"}
