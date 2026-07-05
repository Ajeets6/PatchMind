import argparse
import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

from patchmind.config import Settings
from patchmind.memory.preflight import PreflightChecker, PreflightError
from patchmind.repository.scanner import scan_repository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PATCHMIND_INSTRUCTIONS_START = "<!-- patchmind:start -->"
PATCHMIND_INSTRUCTIONS_END = "<!-- patchmind:end -->"


class SetupError(RuntimeError):
    pass


def _pull_ollama_models(settings: Settings) -> None:
    if not shutil.which("ollama"):
        raise SetupError("Ollama is not installed or is not on PATH: https://ollama.com/download")
    for model in dict.fromkeys((settings.llm_model, settings.embedding_model)):
        print(f"Ensuring Ollama model: {model}")
        result = subprocess.run(["ollama", "pull", model], check=False)
        if result.returncode:
            raise SetupError(
                f"Could not pull Ollama model '{model}'. Start Ollama with 'ollama serve' "
                "and rerun setup."
            )


def _codex_command(root: Path) -> list[str]:
    return [
        "codex",
        "mcp",
        "add",
        "patchmind",
        "--env",
        "PATCHMIND_TRANSPORT=stdio",
        "--env",
        f"PYTHONPATH={root / 'src'}",
        "--",
        "uv",
        "--directory",
        str(root),
        "run",
        "--frozen",
        "python",
        "-m",
        "patchmind.server",
    ]


def _install_codex(root: Path) -> None:
    if not shutil.which("codex"):
        raise SetupError("Codex CLI is not installed or is not on PATH.")
    existing = subprocess.run(
        ["codex", "mcp", "get", "patchmind"], capture_output=True, check=False
    )
    if existing.returncode == 0:
        print("Codex MCP entry 'patchmind' already exists; leaving it unchanged.")
    else:
        result = subprocess.run(_codex_command(root), check=False)
        if result.returncode:
            raise SetupError("Could not add PatchMind to Codex MCP configuration.")
        print("Added PatchMind to Codex MCP configuration.")
    _install_codex_skill(root)
    _install_codex_instructions(root)


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def _install_codex_skill(root: Path) -> Path:
    source = root / "agent-skills" / "patchmind-memory"
    if not (source / "SKILL.md").is_file():
        raise SetupError(f"PatchMind Codex skill not found: {source}")
    target = _codex_home() / "skills" / "patchmind-memory"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    print(f"Installed PatchMind Codex skill: {target}")
    return target


def _install_codex_instructions(root: Path) -> Path:
    source = root / "AGENTS.md"
    if not source.is_file():
        raise SetupError(f"PatchMind Codex instructions not found: {source}")
    block = source.read_text(encoding="utf-8").strip()
    if not (
        block.startswith(PATCHMIND_INSTRUCTIONS_START)
        and block.endswith(PATCHMIND_INSTRUCTIONS_END)
    ):
        raise SetupError("PatchMind AGENTS.md is missing its managed block markers.")

    target = _codex_home() / "AGENTS.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    start = existing.find(PATCHMIND_INSTRUCTIONS_START)
    end = existing.find(PATCHMIND_INSTRUCTIONS_END)
    if (start == -1) != (end == -1) or (start != -1 and end < start):
        raise SetupError(f"Malformed PatchMind instruction block in {target}")
    if start == -1:
        updated = existing.rstrip()
        updated = f"{updated}\n\n{block}\n" if updated else f"{block}\n"
    else:
        end += len(PATCHMIND_INSTRUCTIONS_END)
        updated = existing[:start] + block + existing[end:]
    target.write_text(updated, encoding="utf-8")
    print(f"Installed PatchMind Codex instructions: {target}")
    return target


def _remove_codex_skill() -> None:
    target = _codex_home() / "skills" / "patchmind-memory"
    if target.is_dir():
        shutil.rmtree(target)
        print(f"Removed PatchMind Codex skill: {target}")
    else:
        print(f"PatchMind Codex skill is not installed: {target}")


def _remove_codex_instructions() -> None:
    target = _codex_home() / "AGENTS.md"
    if not target.exists():
        print(f"Global Codex instructions do not exist: {target}")
        return
    existing = target.read_text(encoding="utf-8")
    start = existing.find(PATCHMIND_INSTRUCTIONS_START)
    end = existing.find(PATCHMIND_INSTRUCTIONS_END)
    if start == -1 and end == -1:
        print(f"PatchMind instruction block is not installed: {target}")
        return
    if start == -1 or end == -1 or end < start:
        raise SetupError(f"Malformed PatchMind instruction block in {target}")
    end += len(PATCHMIND_INSTRUCTIONS_END)
    before = existing[:start].rstrip()
    after = existing[end:].strip()
    updated = "\n\n".join(part for part in (before, after) if part)
    if updated:
        target.write_text(updated + "\n", encoding="utf-8")
    else:
        target.unlink()
    print(f"Removed PatchMind Codex instructions: {target}")


def run_uninstall_codex() -> int:
    if not shutil.which("codex"):
        raise SetupError("Codex CLI is not installed or is not on PATH.")
    existing = subprocess.run(
        ["codex", "mcp", "get", "patchmind"], capture_output=True, check=False
    )
    if existing.returncode == 0:
        result = subprocess.run(["codex", "mcp", "remove", "patchmind"], check=False)
        if result.returncode:
            raise SetupError("Could not remove PatchMind from Codex MCP configuration.")
        print("Removed PatchMind from Codex MCP configuration.")
    else:
        print("PatchMind MCP entry is not installed.")
    _remove_codex_skill()
    _remove_codex_instructions()
    print("PatchMind Codex integration removed. Restart Codex to stop the active MCP process.")
    print("Repository memory and local models were preserved.")
    return 0


def run_setup(args: argparse.Namespace) -> int:
    env_path = PROJECT_ROOT / ".env"
    example_path = PROJECT_ROOT / ".env.example"
    if env_path.exists():
        print(f"Using existing configuration: {env_path}")
    else:
        if not example_path.exists():
            raise SetupError(f"Configuration template not found: {example_path}")
        shutil.copyfile(example_path, env_path)
        print(f"Created configuration: {env_path}")

    settings = Settings(_env_file=env_path)
    repository = None
    if args.repository:
        try:
            repository = scan_repository(args.repository)
        except (ValueError, OSError) as error:
            raise SetupError(f"Invalid repository: {error}") from error
        print(f"Repository ready: {repository.root}")

    if settings.patchmind_memory_mode == "local" and settings.llm_provider == "ollama":
        if args.no_pull:
            print("Skipping Ollama model pulls.")
        else:
            _pull_ollama_models(settings)

    try:
        result = asyncio.run(PreflightChecker(settings).run())
    except PreflightError as error:
        raise SetupError(f"Preflight failed: {error}") from error
    print(f"Preflight ready: {result['memory_mode']}")

    if args.install_codex:
        _install_codex(PROJECT_ROOT)

    print("PatchMind setup complete.")
    if repository:
        print(f"Next: restart Codex and begin a coding task in {repository.root}")
    elif not args.install_codex:
        print("Next: rerun with --install-codex and optionally --repository <path>.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m patchmind")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup", help="prepare models, validate config, and configure Codex")
    setup.add_argument("--repository", type=Path, help="Git repository PatchMind will index")
    setup.add_argument("--no-pull", action="store_true", help="do not pull Ollama models")
    setup.add_argument(
        "--install-codex",
        action="store_true",
        help="add the MCP server, skill, and automatic instructions to Codex",
    )
    commands.add_parser("serve", help="run the PatchMind MCP server")
    commands.add_parser(
        "uninstall-codex",
        help="remove the MCP entry, skill, and managed instructions from Codex",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "setup":
            return run_setup(args)
        if args.command == "uninstall-codex":
            return run_uninstall_codex()
        from patchmind.server import main as serve

        serve()
        return 0
    except SetupError as error:
        print(f"PatchMind setup failed: {error}", file=sys.stderr)
        return 1
