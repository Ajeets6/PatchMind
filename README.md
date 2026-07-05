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
- Install the `patchmind-memory` Codex skill with implicit invocation enabled.
- Add or update a managed PatchMind block in the user's global Codex `AGENTS.md`.

It never overwrites an existing `.env`, Codex MCP entry, or unrelated global agent instructions. It
updates only the installed PatchMind skill and its marked instruction block. Starting `serve` alone
does not modify Codex configuration; run `setup --install-codex` once. Use `--no-pull` when models
are managed separately.

## Use it

In Codex, provide an absolute repository path:

```text
Use PatchMind to index C:\path\to\your-repository.
```

For substantive coding tasks, the installed skill automatically indexes the repository, retrieves
relevant history before edits, records tested outcomes, and finalizes useful session memory. The
user does not need to prompt for each MCP call.

You can still request memory explicitly when needed:

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
| `patchmind_get_context` | Retrieve decisions, tests, evidence, and freshness warnings |
| `patchmind_find_previous_attempts` | Group failed, rejected, reverted, and successful attempts |
| `patchmind_record_outcome` | Store an attempt with repository-state and outcome metadata |
| `patchmind_finalize_session` | Promote validated session memory with `improve()` |

`patchmind_record_outcome` automatically captures the current branch, commit, timestamp, and a
content hash for every affected file. Callers can also provide `failure_reason`,
`dependency_versions`, and a concise `summary`. When an outcome is recalled, PatchMind compares
the recorded file hashes and branch with the current repository and appends one of these states:

- `Freshness: active` when the affected files and branch still match.
- `Freshness: potentially_stale` when an affected file changed, disappeared, or the branch changed.
- `Freshness: unknown` for legacy outcomes that do not contain file hashes.

Potentially stale memories remain available as historical evidence; they are not presented as
directly applicable fixes.

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

## Automatic Codex demo

Create a repository whose Git history contains a failed per-request lock, its revert, and the
successful shared-lock replacement:

```powershell
cd G:\Git_repo\PatchMind
python scripts/seed_demo.py .demo/patchmind-demo
$demo = (Resolve-Path .demo/patchmind-demo).Path
```

With Ollama running, perform the one-time installation:

```powershell
uv sync
$env:PYTHONPATH = "$PWD\src"
uv run --frozen python -m patchmind setup `
  --repository $demo `
  --install-codex
codex mcp get patchmind
```

The setup output prints the installed skill and global instruction paths. Verify them if desired:

```powershell
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
Get-Content "$codexHome\skills\patchmind-memory\SKILL.md"
Get-Content "$codexHome\AGENTS.md"
```

Restart Codex, open the demo repository, and submit an ordinary request that does not mention
PatchMind:

```text
Investigate why SessionStore uses a class-level lock instead of creating a lock inside save().
Explain the evidence and do not change files.
```

The agent should automatically call the index, context, and previous-attempt tools. Its answer
should connect the reverted per-request approach to workers holding different locks.

Next, submit a normal implementation request:

```text
Improve the concurrent session regression test so it meaningfully protects the shared-lock design.
Implement the change and run the focused test.
```

The agent should retrieve memory before editing, then record the observed test outcome and finalize
the session. Open a new Codex session and ask:

```text
What previous attempts or test outcomes should I consider before changing SessionStore locking?
```

The finalized outcome should be recalled across the session boundary without an explicit PatchMind
instruction.

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
