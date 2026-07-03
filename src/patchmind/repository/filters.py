from pathlib import Path

IGNORED_DIRS = {
    ".git", ".venv", "node_modules", "dist", "build", "coverage", ".patchmind",
    "__pycache__", ".pytest_cache", ".ruff_cache", ".uv-cache",
}
IGNORED_NAMES = {
    "uv.lock", "poetry.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
}
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".tar", ".7z", ".exe", ".dll", ".so", ".dylib", ".pyc", ".woff", ".woff2",
}


def should_include(path: Path, root: Path, max_bytes: int) -> bool:
    relative = path.relative_to(root)
    if any(part in IGNORED_DIRS for part in relative.parts):
        return False
    if path.name in IGNORED_NAMES or path.suffix.lower() in BINARY_SUFFIXES:
        return False
    try:
        return path.is_file() and path.stat().st_size <= max_bytes
    except OSError:
        return False


def is_test_file(relative_path: str) -> bool:
    path = relative_path.replace("\\", "/").lower()
    name = Path(path).name
    return path.startswith("tests/") or "/tests/" in path or name.startswith("test_") or name.endswith(("_test.py", ".test.js", ".spec.ts", ".spec.js"))
