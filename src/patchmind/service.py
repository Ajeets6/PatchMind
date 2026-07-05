import re
from datetime import UTC, datetime

from patchmind.config import Settings
from patchmind.memory.base import MemoryStore
from patchmind.models import Outcome
from patchmind.prompts import EXTRACTION_PROMPT
from patchmind.repository.formatter import format_attempt, format_commit, format_file
from patchmind.repository.git_history import current_commit, read_recent_commits
from patchmind.repository.index_state import IndexState
from patchmind.repository.scanner import hash_repository_files, read_source_files, scan_repository


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
                [record for _, record in pending],
                repo.dataset,
                custom_prompt=EXTRACTION_PROMPT,
                background=True,
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
            "ingestion": "scheduled" if pending else "unchanged",
            "status": "ready",
        }

    async def get_context(self, repository_path, task, file_paths=None, symbol=None, top_k=10):
        repo = scan_repository(repository_path)
        if not IndexState(repo.root).has_memory:
            return {
                "repository_id": repo.repository_id,
                "task": task,
                "context": [],
                "evidence_count": 0,
                "index_status": "not_indexed",
                "status": "not_found",
            }
        qualifiers = [task]
        if file_paths:
            qualifiers.append("Files: " + ", ".join(file_paths))
        if symbol:
            qualifiers.append("Symbol: " + symbol)
        query = "\n".join(qualifiers)
        records = await self.memory.recall(query, repo.dataset, top_k=max(1, min(top_k, 50)))
        records = [self._with_freshness(record, repo) for record in records]
        return {
            "repository_id": repo.repository_id,
            "task": task,
            "context": records,
            "evidence_count": len(records),
            "index_status": "indexed",
            "status": "found" if records else "not_found",
        }

    async def find_previous_attempts(self, repository_path, problem, file_path=None):
        repo = scan_repository(repository_path)
        grouped = {name: [] for name in ("failed", "rejected", "reverted", "successful", "unknown")}
        if not IndexState(repo.root).has_memory:
            return grouped
        query = f"Previous attempts for: {problem}"
        if file_path:
            query += f"\nFile: {file_path}"
        records = await self.memory.recall(query, repo.dataset, top_k=30)
        for record in records:
            match = re.search(
                r"(?:Outcome|Status):\s*(successful|failed|rejected|reverted|inconclusive)",
                record,
                re.IGNORECASE,
            )
            category = match.group(1).lower() if match else "unknown"
            if category == "inconclusive":
                category = "unknown"
            grouped[category].append(self._with_freshness(record, repo))
        return grouped

    async def record_outcome(
        self, repository_path, session_id, task, approach, outcome, evidence,
        affected_files, tests=None, failure_reason=None, dependency_versions=None, summary=None,
    ):
        repo = scan_repository(repository_path)
        normalized = Outcome(outcome).value
        record = format_attempt(
            repo.name,
            task,
            approach,
            normalized,
            evidence,
            affected_files,
            tests,
            branch=repo.branch,
            commit=current_commit(repo.root),
            recorded_at=datetime.now(UTC).isoformat(),
            file_hashes=hash_repository_files(repo.root, affected_files),
            failure_reason=failure_reason,
            dependency_versions=dependency_versions,
            summary=summary,
        )
        await self.memory.remember([record], repo.dataset, session_id=session_id)
        return {
            "repository_id": repo.repository_id,
            "dataset": repo.dataset,
            "session_id": session_id,
            "outcome": normalized,
            "status": "recorded",
        }

    @staticmethod
    def _with_freshness(record: str, repo) -> str:
        if not record.startswith("PATCH ATTEMPT"):
            return record
        section = re.search(
            r"Affected file hashes:\n(?P<hashes>.*?)(?:\nTests:)", record, re.DOTALL
        )
        if not section:
            return record + "\nFreshness: unknown (legacy memory has no file hashes)\n"
        recorded: dict[str, str] = {}
        for line in section.group("hashes").splitlines():
            match = re.match(r"- (.+): ([a-f0-9]{64}|missing|outside_repository)$", line)
            if match:
                recorded[match.group(1)] = match.group(2)
        if not recorded:
            return record + "\nFreshness: unknown (no affected file hashes supplied)\n"
        current = hash_repository_files(repo.root, list(recorded))
        changed = [path for path, old_hash in recorded.items() if current.get(path) != old_hash]
        recorded_branch = re.search(r"^Branch: (.+)$", record, re.MULTILINE)
        details = [f"recorded commit {PatchMindService._field(record, 'Commit')}"]
        try:
            details.append(f"current commit {current_commit(repo.root)}")
        except ValueError:
            pass
        branch_changed = bool(recorded_branch and recorded_branch.group(1) != repo.branch)
        if branch_changed:
            details.append(f"branch changed to {repo.branch}")
        if changed or branch_changed:
            reasons = []
            if changed:
                reasons.append("changed or missing files: " + ", ".join(changed))
            return record + ("\nFreshness: potentially_stale (" + "; ".join(
                details + reasons
            ) + ")\n")
        return (
            record
            + "\nFreshness: active (affected files are unchanged; "
            + "; ".join(details)
            + ")\n"
        )

    @staticmethod
    def _field(record: str, name: str) -> str:
        match = re.search(rf"^{re.escape(name)}: (.+)$", record, re.MULTILINE)
        return match.group(1) if match else "unknown"

    async def finalize_session(self, repository_path, session_id, summary):
        repo = scan_repository(repository_path)
        summary_record = f"""SESSION SUMMARY

Repository: {repo.name}
Session: {session_id}
Summary: {summary}
Status: validated and finalized
"""
        await self.memory.remember([summary_record], repo.dataset, session_id=session_id)
        await self.memory.improve(repo.dataset, [session_id], background=True)
        state = IndexState(repo.root)
        state.add(f"session:{session_id}")
        state.save()
        return {
            "repository_id": repo.repository_id,
            "dataset": repo.dataset,
            "session_id": session_id,
            "status": "finalization_scheduled",
            "memory_mode": self.settings.patchmind_memory_mode,
            "promotion_strategy": "cognee_improve_background",
        }

    async def forget_repository(self, repository_path):
        repo = scan_repository(repository_path)
        await self.memory.forget(repo.dataset)
        return {"repository_id": repo.repository_id, "dataset": repo.dataset, "status": "forgotten"}
