from patchmind.models import Commit, SourceFile


def format_file(repository: str, branch: str, source: SourceFile) -> str:
    kind = "TEST FILE" if source.is_test else "SOURCE FILE"
    return f"""{kind}

Repository: {repository}
Branch: {branch}
Path: {source.path}
Content hash: {source.content_hash}

Content:
{source.content}
"""


def format_commit(repository: str, commit: Commit) -> str:
    changed = "\n".join(f"- {path}" for path in commit.changed_files) or "- none"
    return f"""COMMIT

Repository: {repository}
Commit: {commit.hash}
Date: {commit.date.date().isoformat()}
Message: {commit.message}
Changed files:
{changed}

Change (limited diff):
{commit.diff or 'No textual diff.'}

Relationships:
Commit modifies the listed files. Tests in the changed files protect related behavior.
"""


def format_attempt(
    repository,
    task,
    approach,
    outcome,
    evidence,
    affected_files,
    tests,
    *,
    branch=None,
    commit=None,
    recorded_at=None,
    file_hashes=None,
    failure_reason=None,
    dependency_versions=None,
    summary=None,
):
    files = "\n".join(f"- {item}" for item in affected_files) or "- none supplied"
    test_lines = "\n".join(f"- {item}" for item in (tests or [])) or "- none supplied"
    hashes = "\n".join(
        f"- {path}: {content_hash}" for path, content_hash in (file_hashes or {}).items()
    ) or "- none supplied"
    dependencies = "\n".join(
        f"- {name}: {version}" for name, version in (dependency_versions or {}).items()
    ) or "- none supplied"
    return f"""PATCH ATTEMPT

Repository: {repository}
Branch: {branch or 'unknown'}
Commit: {commit or 'unknown'}
Recorded at: {recorded_at or 'unknown'}
Task: {task}
Approach: {approach}
Outcome: {outcome}
Evidence: {evidence}
Failure reason: {failure_reason or 'none supplied'}
Summary: {summary or 'none supplied'}
Affected files:
{files}
Affected file hashes:
{hashes}
Tests:
{test_lines}
Dependency versions:
{dependencies}

This attempt must be recalled when modifying related code.
"""
