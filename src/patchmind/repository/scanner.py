import hashlib
import re
from pathlib import Path

from patchmind.models import RepositoryInfo, SourceFile
from patchmind.repository.filters import is_test_file, should_include
from patchmind.repository.git_history import current_branch, repository_root


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "repository"


def create_repository_id(root: Path) -> str:
    canonical = str(root.resolve()).replace("\\", "/").lower()
    return f"{_slug(root.name)}-{hashlib.sha256(canonical.encode()).hexdigest()[:6]}"


def scan_repository(path: str | Path) -> RepositoryInfo:
    root = repository_root(path)
    repository_id = create_repository_id(root)
    return RepositoryInfo(
        root=root,
        name=root.name,
        branch=current_branch(root),
        repository_id=repository_id,
        dataset=f"patchmind_{repository_id.replace('-', '_')}",
    )


def read_source_files(root: Path, max_bytes: int) -> list[SourceFile]:
    files: list[SourceFile] = []
    for path in sorted(root.rglob("*")):
        if not should_include(path, root, max_bytes):
            continue
        try:
            raw = path.read_bytes()
            if b"\x00" in raw[:8192]:
                continue
            content = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root).as_posix()
        files.append(SourceFile(
            path=relative,
            content=content,
            content_hash=hashlib.sha256(raw).hexdigest(),
            is_test=is_test_file(relative),
        ))
    return files
