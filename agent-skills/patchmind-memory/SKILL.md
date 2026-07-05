---
name: patchmind-memory
description: Use PatchMind MCP as persistent development memory during repository coding work. Invoke automatically when diagnosing bugs, changing existing code, revisiting architectural decisions, handling recurring errors, comparing earlier fixes, or completing tested patches in a repository where PatchMind tools are available. Retrieve history before editing and record meaningful successful or failed outcomes after testing.
---

# PatchMind Memory

Use PatchMind without requiring the user to request memory operations explicitly.

## Workflow

1. Determine the absolute Git repository root.
2. Before editing existing behavior, call `patchmind_get_context` with the task and known file paths or symbol.
3. For bugs, regressions, or rejected designs, also call `patchmind_find_previous_attempts`.
4. If both lookups return no evidence, call `patchmind_index_repository` once to schedule background ingestion. Do not wait for newly indexed memory or retry retrieval during the same task; use current files, tests, and Git as evidence. The indexed history is for later tasks.
5. Inspect the current working tree and treat recalled memory as evidence, not authority. Verify `potentially_stale` records against current code and dependencies.
6. After each meaningful tested approach, call `patchmind_record_outcome`. Record failures as well as successes. Include affected files, tests, concrete evidence, failure reason, dependency versions, and a concise summary when known.
7. When the task has a validated conclusion, call `patchmind_finalize_session` once so useful outcomes persist across sessions.

For `patchmind_record_outcome`, use exactly one supported outcome value: `successful`, `failed`, `rejected`, `reverted`, or `inconclusive`. Never use synonyms such as `success`, `succeeded`, `failure`, or `passed`.

Use a stable, task-specific session ID such as `<repository>-<task>-<date>` and reuse it for all attempts in the same task.

## Guardrails

- If PatchMind tools are unavailable, continue the coding task and state that persistent memory was skipped. Do not repeatedly retry unavailable tools.
- Do not index or store secrets, credentials, generated dependencies, or unrelated repositories.
- Do not record speculative outcomes. Record observed results from tests, builds, review, or reproducible failures.
- For read-only investigation, explanation, review, or status tasks, do not call `patchmind_record_outcome` or `patchmind_finalize_session`. There is no patch outcome to store.
- Do not finalize a session before its recorded evidence is complete.
- Treat `finalization_scheduled` as success. Promotion continues in the MCP server background; do not wait or retry.
- Never block the current investigation waiting for repository indexing to finish.
- Treat an empty tool result or `not_indexed` status as a completed lookup with no evidence. Never describe it as still running and never wait for it.
