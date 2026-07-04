import argparse
import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

from patchmind.config import Settings
from patchmind.memory.preflight import PreflightChecker, PreflightError
from patchmind.repository.scanner import scan_repository

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
        return
    result = subprocess.run(_codex_command(root), check=False)
    if result.returncode:
        raise SetupError("Could not add PatchMind to Codex MCP configuration.")
    print("Added PatchMind to Codex MCP configuration.")


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
        print(f"Next: ask Codex to index {repository.root}")
    elif not args.install_codex:
        print("Next: rerun with --install-codex and optionally --repository <path>.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m patchmind")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup", help="prepare models, validate config, and configure Codex")
    setup.add_argument("--repository", type=Path, help="Git repository PatchMind will index")
    setup.add_argument("--no-pull", action="store_true", help="do not pull Ollama models")
    setup.add_argument("--install-codex", action="store_true", help="add PatchMind to Codex MCP")
    commands.add_parser("serve", help="run the PatchMind MCP server")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "setup":
            return run_setup(args)
        from patchmind.server import main as serve

        serve()
        return 0
    except SetupError as error:
        print(f"PatchMind setup failed: {error}", file=sys.stderr)
        return 1
