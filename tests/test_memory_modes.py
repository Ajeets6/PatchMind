import sys
from types import SimpleNamespace

import pytest

from patchmind.config import Settings
from patchmind.memory.cognee_store import CogneeMemoryStore


class FakeCognee:
    def __init__(self):
        self.serve_calls = []

    async def serve(self, **kwargs):
        self.serve_calls.append(kwargs)


def test_local_mode_is_default_and_ignores_cloud_url(monkeypatch, tmp_path):
    fake = FakeCognee()
    monkeypatch.setitem(sys.modules, "cognee", fake)
    settings = Settings(
        cognee_service_url="https://unused.example",
        patchmind_cognee_data_dir=tmp_path / "data",
        patchmind_cognee_system_dir=tmp_path / "system",
    )

    with pytest.warns(RuntimeWarning, match="ignored"):
        store = CogneeMemoryStore(settings)

    assert settings.patchmind_memory_mode == "local"
    assert store.client is fake
    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "system").is_dir()


async def test_cloud_mode_is_explicit_and_warns_about_improve(monkeypatch):
    fake = FakeCognee()
    monkeypatch.setitem(sys.modules, "cognee", fake)
    settings = Settings(
        patchmind_memory_mode="cloud",
        cognee_service_url="https://tenant.example",
        cognee_api_key="secret",
    )

    with pytest.warns(RuntimeWarning, match="improve"):
        store = CogneeMemoryStore(settings)
    await store._connect()

    assert fake.serve_calls == [{"url": "https://tenant.example", "api_key": "secret"}]


def test_cloud_mode_requires_service_url(monkeypatch):
    monkeypatch.setitem(sys.modules, "cognee", SimpleNamespace())
    with pytest.raises(ValueError, match="COGNEE_SERVICE_URL"):
        CogneeMemoryStore(
            Settings(patchmind_memory_mode="cloud", cognee_service_url=None)
        )
