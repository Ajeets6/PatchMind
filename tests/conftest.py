import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def demo_repository(tmp_path: Path) -> Path:
    repo = tmp_path / "demo-repository"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "docs").mkdir()
    (repo / "src" / "session_store.py").write_text(
        "from threading import Lock\n\nclass SessionStore:\n    lock = Lock()\n",
        encoding="utf-8",
    )
    (repo / "src" / "workers.py").write_text("WORKERS = 4\n", encoding="utf-8")
    (repo / "tests" / "test_concurrent_sessions.py").write_text(
        "def test_concurrent_sessions():\n    assert True\n", encoding="utf-8"
    )
    (repo / "docs" / "architecture.md").write_text(
        "# Locking\nUse one process-level SessionStore lock. Per-request locks failed.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "demo@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "PatchMind Demo"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Use process-level lock after per-request failure"], cwd=repo, check=True, capture_output=True)
    return repo
