from patchmind.repository.formatter import format_attempt


def test_attempt_format_preserves_engineering_evidence():
    record = format_attempt(
        "demo", "Fix corruption", "one lock per request", "failed",
        "workers held different locks", ["src/session_store.py"], ["test_concurrent_sessions"],
    )
    assert "Outcome: failed" in record
    assert "one lock per request" in record
    assert "test_concurrent_sessions" in record
