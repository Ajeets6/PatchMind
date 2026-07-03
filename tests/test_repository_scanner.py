from patchmind.repository.scanner import read_source_files, scan_repository


def test_scanner_finds_repository_and_tests(demo_repository):
    info = scan_repository(demo_repository / "src")
    files = read_source_files(info.root, 100_000)
    assert info.name == "demo-repository"
    assert info.dataset.startswith("patchmind_demo_repository_")
    assert any(item.path == "src/session_store.py" for item in files)
    assert any(item.path == "tests/test_concurrent_sessions.py" and item.is_test for item in files)


def test_scanner_skips_ignored_and_binary_files(demo_repository):
    (demo_repository / "node_modules").mkdir()
    (demo_repository / "node_modules" / "ignored.js").write_text("ignored")
    (demo_repository / "image.png").write_bytes(b"not really an image")
    paths = {item.path for item in read_source_files(demo_repository, 100_000)}
    assert "node_modules/ignored.js" not in paths
    assert "image.png" not in paths
