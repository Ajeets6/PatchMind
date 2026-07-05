import subprocess
from types import SimpleNamespace

from patchmind.repository.git_history import git


def test_git_subprocess_never_inherits_mcp_stdin(monkeypatch, tmp_path):
    captured = {}

    def run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="main\n", stderr="")

    monkeypatch.setattr(subprocess, "run", run)

    assert git(tmp_path, "branch", "--show-current") == "main\n"
    assert captured["command"] == [
        "git",
        "-C",
        str(tmp_path),
        "branch",
        "--show-current",
    ]
    assert captured["kwargs"]["stdin"] is subprocess.DEVNULL
