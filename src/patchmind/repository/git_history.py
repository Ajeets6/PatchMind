import subprocess
from datetime import datetime
from pathlib import Path

from patchmind.models import Commit


class GitError(ValueError):
    pass


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace", check=False,
    )
    if check and result.returncode:
        raise GitError(result.stderr.strip() or "Git command failed")
    return result.stdout


def repository_root(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    if not candidate.exists():
        raise ValueError(f"Repository path does not exist: {candidate}")
    return Path(git(candidate, "rev-parse", "--show-toplevel").strip()).resolve()


def current_branch(root: Path) -> str:
    return git(root, "branch", "--show-current").strip() or "detached"


def current_commit(root: Path) -> str:
    return git(root, "rev-parse", "HEAD").strip()


def read_recent_commits(root: Path, limit: int, max_diff_chars: int = 4_000) -> list[Commit]:
    if limit <= 0:
        return []
    output = git(root, "log", f"-n{limit}", "--format=%H%x1f%aI%x1f%s%x1e", check=False)
    commits: list[Commit] = []
    for record in output.strip("\n\x1e").split("\x1e") if output else []:
        fields = record.strip().split("\x1f", 2)
        if len(fields) != 3:
            continue
        commit_hash, date, message = fields
        names = git(root, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit_hash)
        diff = git(root, "show", "--format=", "--no-ext-diff", "--unified=2", commit_hash)
        commits.append(Commit(
            hash=commit_hash,
            date=datetime.fromisoformat(date),
            message=message.strip(),
            changed_files=tuple(line for line in names.splitlines() if line),
            diff=diff[:max_diff_chars],
        ))
    return commits
