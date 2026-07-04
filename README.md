# PatchMind

PatchMind is an MCP server that gives coding agents persistent repository memory. It indexes code,
tests, documentation, and Git history so an agent can recall earlier decisions and failed approaches
before making another change.

```text
Codex / MCP Inspector -> PatchMind -> Git repository
                                  -> Cognee -> Ollama or OpenAI-compatible API
```

Local Cognee with Ollama is the default. Validated session outcomes are promoted with
`improve(session_ids=...)`, allowing them to survive a Codex restart.

## Quick start

Requirements: Python 3.12+, `uv`, Git, Ollama, and Codex CLI.

Start Ollama in a separate terminal:

```bash
ollama serve
```

Install dependencies and run guided setup from the PatchMind directory:

```powershell
uv sync
$env:PYTHONPATH="src"
uv run --frozen python -m patchmind setup `
  --repository C:\path\to\your-repository `
  --install-codex
```

On Unix, use `export PYTHONPATH=src` and replace PowerShell backticks with `\`.

Setup will:

- Create `.env` when it does not exist.
- Pull `qwen2.5-coder:7b` and `nomic-embed-text` when missing.
- Validate Ollama, model names, embedding dimensions, and the Git repository.
- Add PatchMind to Codex using absolute paths.

It never overwrites an existing `.env` or Codex MCP entry. Use `--no-pull` when models are managed
separately.

## Use it

In Codex, provide an absolute repository path:

```text
Use PatchMind to index C:\path\to\your-repository.
```

Then ask:

```text
Before changing SessionStore, check PatchMind for previous attempts.
```

After testing a change:

```text
Record this outcome in PatchMind, then finalize the session.
```

PatchMind exposes five tools:

| Tool | Purpose |
| --- | --- |
| `patchmind_index_repository` | Index files and recent commits |
| `patchmind_get_context` | Retrieve decisions, tests, and evidence |
| `patchmind_find_previous_attempts` | Group failed, rejected, reverted, and successful attempts |
| `patchmind_record_outcome` | Store an attempt in session memory |
| `patchmind_finalize_session` | Promote validated session memory with `improve()` |

## Provider configuration

The default Ollama settings are in [.env.example](.env.example). PatchMind performs startup checks
and prints commands for missing models or configuration errors.

To use OpenAI instead, update `.env`:

```env
PATCHMIND_MEMORY_MODE=local
LLM_PROVIDER=openai
LLM_MODEL=openai/gpt-4.1-mini
LLM_ENDPOINT=https://api.openai.com/v1
LLM_API_KEY=your-openai-api-key
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_ENDPOINT=https://api.openai.com/v1
EMBEDDING_API_KEY=your-openai-api-key
EMBEDDING_DIMENSIONS=1536
```

An OpenAI API key is separate from a ChatGPT subscription. Other OpenAI-compatible services can
use `LLM_PROVIDER=custom` and `EMBEDDING_PROVIDER=openai_compatible`.

Cognee Cloud is optional:

```env
PATCHMIND_MEMORY_MODE=cloud
COGNEE_SERVICE_URL=https://your-tenant.aws.cognee.ai
COGNEE_API_KEY=your-cognee-key
```

Cloud mode requires the tenant to expose `POST /api/v1/improve`; startup fails clearly when it
does not.

## Run and deploy

Run Streamable HTTP locally at `http://localhost:8000/mcp`:

```powershell
$env:PYTHONPATH="src"
uv run --frozen python -m patchmind serve
```

Run the complete Docker demo:

```bash
uv run --frozen python scripts/seed_demo.py .demo/patchmind-demo
docker compose up --build
```

Compose starts Ollama, pulls both models, persists Cognee data, and mounts the demo repository at
`/repositories/patchmind-demo`. Download the models before presenting because the first pull can
take several minutes.

For another repository, mount it read-write into the PatchMind container and pass its container
path to the MCP tool. Read-write access is required for `.patchmind/index.json` deduplication state.

## Demo flow

1. Index the generated demo repository.
2. Ask why `SessionStore` uses a process-level lock.
3. Recall that per-request locking was previously reverted.
4. Record a new failed attempt and finalize the session.
5. Restart Codex and recall the same lesson.

## Tests

```bash
uv run --frozen pytest
uv run --frozen ruff check .
```

Optional live tests:

```bash
PATCHMIND_RUN_COGNEE_LOCAL_INTEGRATION=1 uv run pytest tests/test_cognee_local_integration.py -v
PATCHMIND_RUN_COGNEE_CLOUD_INTEGRATION=1 uv run pytest tests/test_cognee_integration.py -v
```

## Privacy

Each repository uses an isolated Cognee dataset. PatchMind excludes `.git`, dependencies, virtual
environments, build output, binary files, lockfiles, oversized files, and undecodable content.
