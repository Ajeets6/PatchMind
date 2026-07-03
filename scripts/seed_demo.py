import argparse
import shutil
import subprocess
from pathlib import Path


def run(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def commit(repo: Path, message: str) -> None:
    run(repo, "add", ".")
    run(repo, "commit", "-m", message)


def seed(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    run(target, "init")
    run(target, "config", "user.email", "demo@patchmind.local")
    run(target, "config", "user.name", "PatchMind Demo")

    write(target / "src/session_store.py", "class SessionStore:\n    def save(self, value):\n        self.value = value\n")
    commit(target, "Basic session store")

    write(target / "src/workers.py", "from concurrent.futures import ThreadPoolExecutor\n\nWORKERS = ThreadPoolExecutor(4)\n")
    commit(target, "Add concurrent workers")

    write(target / "src/session_store.py", "from threading import Lock\n\nclass SessionStore:\n    def save(self, value):\n        lock = Lock()\n        with lock:\n            self.value = value\n")
    commit(target, "Attempt one lock per request")

    write(target / "src/session_store.py", "class SessionStore:\n    def save(self, value):\n        self.value = value\n")
    write(target / "docs/architecture.md", "# Session writes\nPer-request locking was reverted because workers held different locks.\n")
    commit(target, "Revert per-request locking because concurrency still fails")

    write(target / "src/session_store.py", "from threading import Lock\n\nclass SessionStore:\n    _lock = Lock()\n    def save(self, value):\n        with self._lock:\n            self.value = value\n")
    commit(target, "Introduce process-level SessionStore lock")

    write(target / "tests/test_concurrent_sessions.py", "def test_concurrent_sessions():\n    # Regression coverage for shared locking.\n    assert True\n")
    commit(target, "Add concurrent session regression test")
    print(target.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    seed(parser.parse_args().target.resolve())
