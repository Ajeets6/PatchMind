from argparse import Namespace
from types import SimpleNamespace

from patchmind import cli


class ReadyChecker:
    def __init__(self, settings):
        self.settings = settings

    async def run(self):
        return {"status": "ready", "memory_mode": "cloud"}


def test_setup_creates_env_and_runs_preflight(monkeypatch, tmp_path, capsys):
    (tmp_path / ".env.example").write_text("PATCHMIND_MEMORY_MODE=cloud\n", encoding="utf-8")
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        cli,
        "Settings",
        lambda **kwargs: SimpleNamespace(
            patchmind_memory_mode="cloud", llm_provider="openai"
        ),
    )
    monkeypatch.setattr(cli, "PreflightChecker", ReadyChecker)

    result = cli.run_setup(
        Namespace(repository=None, no_pull=False, install_codex=False)
    )

    assert result == 0
    assert (tmp_path / ".env").is_file()
    assert "PatchMind setup complete" in capsys.readouterr().out


def test_codex_command_uses_absolute_project_paths(tmp_path):
    command = cli._codex_command(tmp_path.resolve())
    assert f"PYTHONPATH={tmp_path.resolve() / 'src'}" in command
    assert command[command.index("--directory") + 1] == str(tmp_path.resolve())


def test_default_model_is_coder_model():
    from patchmind.config import Settings

    assert Settings(_env_file=None).llm_model == "qwen2.5-coder:7b"
