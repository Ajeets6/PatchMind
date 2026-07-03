from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class Outcome(StrEnum):
    SUCCESSFUL = "successful"
    FAILED = "failed"
    REJECTED = "rejected"
    REVERTED = "reverted"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class RepositoryInfo:
    root: Path
    name: str
    branch: str
    repository_id: str
    dataset: str


@dataclass(frozen=True)
class SourceFile:
    path: str
    content: str
    content_hash: str
    is_test: bool = False


@dataclass(frozen=True)
class Commit:
    hash: str
    date: datetime
    message: str
    changed_files: tuple[str, ...] = field(default_factory=tuple)
    diff: str = ""
