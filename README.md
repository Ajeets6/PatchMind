# PatchMind

PatchMind is an MCP server that gives coding agents durable, repository-specific memory. It indexes source, tests, documentation, and bounded Git history; recalls decisions and failed approaches before edits; and promotes validated coding-session outcomes into permanent Cognee memory.

## Problem

Coding agents lose repository history when a context window or session ends. Plausible changes can repeat an approach that reviewers rejected, a commit reverted, or a regression test already disproved.

## Solution

PatchMind turns repository evidence and observed coding outcomes into scoped memory that an agent retrieves before editing. Its stable responses retain commit, file, test, outcome, and evidence fields instead of returning raw Git logs.

## Why persistent repository memory matters

The useful unit is an engineering lesson, not a chat transcript. PatchMind keeps noisy attempts in session memory and promotes them only when a session is finalized, allowing a fresh agent session to avoid a known failure without inheriting the previous context window.

## Architecture

```text
Codex / MCP Inspector -- Streamable HTTP or stdio --> PatchMind
                                                        |-- Git + filesystem
                                                        `-- Local Cognee (default)
                                                              `-- OpenAI-compatible LLM
```

Cloud Cognee is an explicit compatibility mode. It is usable only when the tenant exposes
`POST /api/v1/improve`.

PatchMind exposes workflows rather than generic memory aliases:

- `patchmind_index_repository` indexes filtered files and recent commits.
- `patchmind_get_context` retrieves grounded evidence for a task.
- `patchmind_find_previous_attempts` groups attempts by outcome.
- `patchmind_record_outcome` writes an attempt to isolated session memory.
- `patchmind_finalize_session` promotes a validated session with `improve()`.

## Cognee lifecycle

| PatchMind event | Cognee operation |
| --- | --- |
| Index repository history | `remember()` |
| Retrieve past decisions | `recall()` |
| Record active coding attempt | `remember(session_id=...)` |
| Consolidate validated session | `improve(session_ids=...)` |
| Delete repository memory | `forget(dataset=...)` (service API, not an MCP tool) |

## Installation

Requirements: Python 3.12+, `uv`, Git, and either Ollama or an OpenAI-compatible model API.

```bash
uv sync
copy .env.example .env  # Windows; use cp on Unix
```

Local Cognee is the default because PatchMind requires explicit
[`improve(session_ids=...)`](https://docs.cognee.ai/api-reference/improve/improve#improve)
to promote only validated sessions. `record_outcome` disables automatic improvement so noisy
attempts remain provisional until `finalize_session`.

### Ollama profile (default)

Ollama uses its OpenAI-compatible chat endpoint. Start it and pull the two demo models:

```bash
ollama serve
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

The defaults in `.env.example` are:

```env
PATCHMIND_MEMORY_MODE=local
COGNEE_SKIP_CONNECTION_TEST=true
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
LLM_ENDPOINT=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MAX_COMPLETION_TOKENS=4096
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_ENDPOINT=http://localhost:11434/v1
EMBEDDING_API_KEY=ollama
EMBEDDING_DIMENSIONS=768
```

### OpenAI profile

Local Cognee can use OpenAI-hosted models without changing PatchMind code:

```env
PATCHMIND_MEMORY_MODE=local
LLM_PROVIDER=openai
LLM_MODEL=openai/gpt-4.1-mini
LLM_ENDPOINT=https://api.openai.com/v1
LLM_API_KEY=your-openai-api-key
LLM_MAX_COMPLETION_TOKENS=4096
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_ENDPOINT=https://api.openai.com/v1
EMBEDDING_API_KEY=your-openai-api-key
EMBEDDING_DIMENSIONS=1536
```

An OpenAI API key is separate from a ChatGPT subscription. Other OpenAI-compatible services can
use `LLM_PROVIDER=custom` and `EMBEDDING_PROVIDER=openai_compatible` with their endpoint, model,
key, and exact embedding dimensions. These names follow Cognee's
[provider environment variables](https://docs.cognee.ai/setup-configuration/llm-providers#environment-variables).

### Cloud compatibility mode

```env
PATCHMIND_MEMORY_MODE=cloud
COGNEE_SERVICE_URL=https://your-tenant.aws.cognee.ai
COGNEE_API_KEY=your-cognee-key
```

Cloud mode emits a startup warning because older tenants omit `/api/v1/improve`. A configured
cloud URL is intentionally ignored unless `PATCHMIND_MEMORY_MODE=cloud` is set.

Run Streamable HTTP at `http://localhost:8000/mcp`:

```bash
$env:PYTHONPATH="src"; uv run --frozen python -m patchmind.server  # PowerShell
# PYTHONPATH=src uv run --frozen python -m patchmind.server       # Unix
```

For stdio, set `PATCHMIND_TRANSPORT=stdio` before starting.

## Codex setup

Local stdio:

```bash
codex mcp add patchmind --env PATCHMIND_TRANSPORT=stdio --env PYTHONPATH=src -- uv run --frozen python -m patchmind.server
codex mcp list
```

Deployed Streamable HTTP:

```bash
codex mcp add patchmind --url https://your-domain.example/mcp
```

The same configuration is available to Codex CLI and IDE. For Inspector testing, start the server and run `npx -y @modelcontextprotocol/inspector`, then connect to `http://localhost:8000/mcp`.

## Demo

Create the controlled six-commit repository, then index it:

```bash
uv run --frozen python scripts/seed_demo.py .demo/patchmind-demo
$env:PYTHONPATH="src"; uv run --frozen python scripts/run_demo.py .demo/patchmind-demo
```

The history demonstrates a per-request lock that was reverted after a concurrency failure, followed by a process-level lock and regression test. In Codex, call `patchmind_get_context` before changing `SessionStore`, record a new result with `patchmind_record_outcome`, finalize it, restart Codex, and retrieve the lesson again.

### Demo-ready deployment options

1. **Codex stdio:** fastest and least failure-prone; Codex launches PatchMind directly.
2. **Local HTTP:** run PatchMind at `http://localhost:8000/mcp` for Codex and MCP Inspector.
3. **Docker Compose:** starts Ollama, pulls both models, starts PatchMind, and persists both
   Cognee and Ollama data:

```bash
uv run --frozen python scripts/seed_demo.py .demo/patchmind-demo
docker compose up --build
```

The demo repository is mounted at `/repositories/patchmind-demo`. First model download can take
several minutes; run it before presenting. Subsequent starts reuse named volumes.
Local mode skips Cognee's fixed 30-second connection probe because cold-starting a local model can
exceed that timeout; the first real indexing operation still validates the model endpoint.

For a hosted deployment, expose only PatchMind's `/mcp` endpoint through platform HTTPS and keep
the Cognee volume persistent. Ollama can run on the same private network or be replaced with an
OpenAI-compatible hosted provider.

## Indexing and privacy

Each canonical repository path gets a stable, isolated dataset name. PatchMind excludes `.git`, virtual environments, dependencies, build output, coverage, binary files, lockfiles, oversized files, and undecodable content. Limited diffs avoid uploading huge patches. Deduplication keys are stored in `.patchmind/index.json`; add `.patchmind/` to repositories that do not already ignore it.

The internal `PatchMindService.forget_repository()` deletes a complete repository dataset. It is deliberately not exposed as a sixth MCP tool while the five core tools remain the frozen interface. Deleting the local `.patchmind/index.json` after forgetting allows a full re-index.

## Technical decisions

- Git CLI is used for predictable history extraction and no additional Git abstraction.
- Records use explicit commit, file, test, attempt, outcome, and evidence fields before Cognee extraction.
- Session writes set `self_improvement=False`; finalization is the explicit promotion gate.
- The memory protocol and deterministic in-memory implementation keep core workflows testable without cloud credentials.

## Tests and Docker

```bash
uv run pytest
uv run ruff check .
docker build -t patchmind .
docker run --rm -p 8000:8000 --env-file .env -v patchmind-data:/data -v /path/to/repos:/repos patchmind
```

Run the opt-in live Cognee lifecycle test with configured credentials:

```bash
PATCHMIND_RUN_COGNEE_LOCAL_INTEGRATION=1 uv run pytest tests/test_cognee_local_integration.py -v
PATCHMIND_RUN_COGNEE_CLOUD_INTEGRATION=1 uv run pytest tests/test_cognee_integration.py -v
```

The live test is also a compatibility gate: the configured tenant must expose
`POST /api/v1/improve`. Older Cognee API deployments that only expose
`remember`, `recall`, and `forget` cannot perform PatchMind's required explicit
session-to-permanent promotion.

Repository paths passed to a container must be mounted into it. Cloud integration requires valid Cognee credentials and is intentionally separate from deterministic unit tests.

## Roadmap

Post-hackathon work includes a VS Code extension, GitHub/GitLab webhooks, multi-user authentication and repository permissions, graph visualization, broad AST parsing, automatic PR comments, background synchronization, and fine-grained deletion.
