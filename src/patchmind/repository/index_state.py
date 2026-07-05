import json
from pathlib import Path


class IndexState:
    def __init__(self, root: Path) -> None:
        self.path = root / ".patchmind" / "index.json"
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.keys = set(data.get("keys", []))
        except (OSError, ValueError):
            self.keys: set[str] = set()

    def unseen(self, key: str) -> bool:
        return key not in self.keys

    @property
    def has_memory(self) -> bool:
        return bool(self.keys)

    def add(self, key: str) -> None:
        self.keys.add(key)

    def save(self) -> None:
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps({"keys": sorted(self.keys)}, indent=2), encoding="utf-8")
