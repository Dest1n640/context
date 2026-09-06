"""Smoke and regression tests for llmctx."""

import subprocess
import sys
from pathlib import Path

import pytest

import llmctx


def run(tmp_path, *args):
    """Run llmctx.main against tmp_path, return (exit_code, output_text)."""
    out = tmp_path / "out.md"
    code = llmctx.main([str(tmp_path), str(out), *args])
    text = out.read_text(encoding="utf-8") if out.exists() else ""
    return code, text


def write(base: Path, rel: str, content: str):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_basic_run_collects_files(tmp_path):
    write(tmp_path, "main.py", "print('hi')\n")
    write(tmp_path, "docs/guide.md", "# Guide\n")
    code, text = run(tmp_path, "--no-git")
    assert code == 0
    assert "## Structure" in text
    assert "### `main.py`" in text
    assert "print('hi')" in text
    # docs sort before code in the Contents section
    assert text.index("### `docs/guide.md`") < text.index("### `main.py`")


def test_secret_name_is_excluded(tmp_path):
    write(tmp_path, "app.py", "x = 1\n")
    write(tmp_path, ".env", "TOKEN=supersecretvalue\n")
    write(tmp_path, "server.pem", "-----BEGIN PRIVATE KEY-----\n")
    code, text = run(tmp_path, "--no-git")
    assert code == 0
    assert ".env" not in text
    assert "server.pem" not in text
    assert "supersecretvalue" not in text


def test_secret_content_is_flagged_and_redacted(tmp_path, capsys):
    write(tmp_path, "settings.py",
          "DEBUG = True\nAWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMIK7MDENGbPxRfiCY'\n")
    code, text = run(tmp_path, "--no-git")
    assert code == 0
    assert "wJalrXUtnFEMIK7MDENGbPxRfiCY" in text  # warned, not removed
    err = capsys.readouterr().err
    assert "possible secret" in err

    code, text = run(tmp_path, "--no-git", "--redact")
    assert code == 0
    assert "wJalrXUtnFEMIK7MDENGbPxRfiCY" not in text
    assert llmctx.REDACTION_MARKER in text
    assert "redacted" in text.lower()


def test_binary_file_is_skipped(tmp_path, capsys):
    write(tmp_path, "readme.txt", "hello\n")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00binary")
    code, text = run(tmp_path, "--no-git")
    assert code == 0
    assert "### `logo.png`" not in text
    assert "binary" in capsys.readouterr().err


def test_max_bytes_truncates(tmp_path):
    write(tmp_path, "big.txt", "line\n" * 5000)
    code, text = run(tmp_path, "--no-git", "--max-bytes", "200")
    assert code == 0
    assert "truncated by --max-bytes" in text
    assert "_(truncated)_" in text


def test_exclude_and_include_globs(tmp_path):
    write(tmp_path, "keep.py", "a = 1\n")
    write(tmp_path, "tests/test_x.py", "b = 2\n")
    _, text = run(tmp_path, "--no-git", "--exclude", "tests/**")
    assert "### `keep.py`" in text
    assert "test_x.py" not in text

    _, text = run(tmp_path, "--no-git", "--include", "*.py", "--exclude", "keep.py")
    assert "### `tests/test_x.py`" in text
    assert "### `keep.py`" not in text


def test_backtick_fence_escaping(tmp_path):
    write(tmp_path, "note.md", "Example:\n``````\ncode\n``````\n")
    _, text = run(tmp_path, "--no-git")
    fence = llmctx.fence_for("``````")
    assert len(fence) >= 7
    assert fence + "markdown" in text


def test_llmctxignore_file(tmp_path):
    write(tmp_path, "app.py", "a = 1\n")
    write(tmp_path, "vendor/lib.py", "b = 2\n")
    write(tmp_path, ".llmctxignore", "vendor/\n")
    _, text = run(tmp_path, "--no-git")
    assert "### `app.py`" in text
    assert "vendor/lib.py" not in text


def test_git_mode_honours_gitignore(tmp_path):
    if not _have_git():
        pytest.skip("git not available")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    write(tmp_path, "app.py", "a = 1\n")
    write(tmp_path, "build/out.js", "compiled\n")
    write(tmp_path, ".gitignore", "build/\n")
    code, text = run(tmp_path)
    assert code == 0
    assert "git (`git ls-files`" in text
    assert "### `app.py`" in text
    assert "build/out.js" not in text


def test_output_file_not_included(tmp_path):
    write(tmp_path, "a.py", "x = 1\n")
    out = tmp_path / "ctx.md"
    llmctx.main([str(tmp_path), str(out), "--no-git"])
    llmctx.main([str(tmp_path), str(out), "--no-git"])  # run twice
    text = out.read_text(encoding="utf-8")
    assert "### `ctx.md`" not in text


def test_cli_rejects_missing_directory(tmp_path, capsys):
    code = llmctx.main([str(tmp_path / "nope"), str(tmp_path / "o.md")])
    assert code == 1
    assert "not a directory" in capsys.readouterr().err


def test_runs_as_script(tmp_path):
    write(tmp_path, "x.py", "y = 1\n")
    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, str(root / "llmctx.py"), str(tmp_path),
         str(tmp_path / "o.md"), "--no-git"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert (tmp_path / "o.md").is_file()


def _have_git() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False
