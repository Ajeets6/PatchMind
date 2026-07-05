---
name: patchmind-memory
description: Use PatchMind MCP as persistent development memory during repository coding work. Invoke automatically when diagnosing bugs, changing existing code, revisiting architectural decisions, handling recurring errors, comparing earlier fixes, or completing tested patches in a repository where PatchMind tools are available. Retrieve history before editing and record meaningful successful or failed outcomes after testing.
---

# PatchMind Memory

Use PatchMind without requiring the user to request memory operations explicitly.

## Workflow

1. Determine the absolute Git repository root.
2. At the first substantive task in a repository, call `patchmind_index_repository`. Repeated calls are safe because indexing deduplicates unchanged records.
3. Before editing existing behavior, call `patchmind_get_context` with the task and known file paths or symbol.
4. For bugs, regressions, or rejected designs, also call `patchmind_find_previous_attempts`.
5. Inspect the current working tree and treat recalled memory as evidence, not authority. Verify `potentially_stale` records against current code and dependencies.
6. After each meaningful tested approach, call `patchmind_record_outcome`. Record failures as well as successes. Include affected files, tests, concrete evidence, failure reason, dependency versions, and a concise summary when known.
7. When the task has a validated conclusion, call `patchmind_finalize_session` once so useful outcomes persist across sessions.

Use a stable, task-specific session ID such as `<repository>-<task>-<date>` and reuse it for all attempts in the same task.

## Guardrails

- If PatchMind tools are unavailable, continue the coding task and state that persistent memory was skipped. Do not repeatedly retry unavailable tools.
- Do not index or store secrets, credentials, generated dependencies, or unrelated repositories.
- Do not record speculative outcomes. Record observed results from tests, builds, review, or reproducible failures.
- Do not finalize a session before its recorded evidence is complete.
