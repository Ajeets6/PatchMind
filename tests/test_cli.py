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


def test_install_codex_skill_uses_codex_home(monkeypatch, tmp_path):
    project = tmp_path / "project"
    source = project / "agent-skills" / "patchmind-memory"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: patchmind-memory\n---\n", encoding="utf-8")
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    target = cli._install_codex_skill(project)

    assert target == codex_home / "skills" / "patchmind-memory"
    assert (target / "SKILL.md").read_text(encoding="utf-8").startswith("---")


def test_install_codex_instructions_preserves_existing_content(monkeypatch, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    block = (
        f"{cli.PATCHMIND_INSTRUCTIONS_START}\n"
        "## PatchMind instructions\nFirst version.\n"
        f"{cli.PATCHMIND_INSTRUCTIONS_END}\n"
    )
    (project / "AGENTS.md").write_text(block, encoding="utf-8")
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    target = codex_home / "AGENTS.md"
    target.write_text("# Existing instructions\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    cli._install_codex_instructions(project)
    first = target.read_text(encoding="utf-8")
    (project / "AGENTS.md").write_text(
        block.replace("First version.", "Updated version."), encoding="utf-8"
    )
    cli._install_codex_instructions(project)
    second = target.read_text(encoding="utf-8")

    assert first.startswith("# Existing instructions")
    assert "Updated version." in second
    assert second.count(cli.PATCHMIND_INSTRUCTIONS_START) == 1
