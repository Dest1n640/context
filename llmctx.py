#!/usr/bin/env python3
"""llmctx — collect a project directory into a single Markdown file for LLMs.

Cross-platform (macOS / Linux / Windows), Python 3.8+, standard library only.
No third-party dependencies: download this one file and run it.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

VERSION = "0.1.0"
DEFAULT_OUTPUT = "context.md"

# --------------------------------------------------------------------------- #
# Ignore patterns                                                            #
# --------------------------------------------------------------------------- #

# Secret-ish file names. Excluded in every mode (even if tracked by git).
SECRET_NAME_PATTERNS = [
    ".env", ".env.*", "*.env",
    "*.pem", "*.key", "*.pfx", "*.p12", "*.keystore", "*.jks",
    "id_rsa", "id_rsa.*", "id_ed25519", "id_ed25519.*", "id_dsa", "id_ecdsa",
    ".pgpass", ".netrc", "_netrc", ".npmrc", ".pypirc",
    "secret.*", "secrets.*", "*.secret", "*.secrets", "*credentials*",
    ".aws/", ".ssh/", ".gnupg/",
]

# Pure noise: never useful in an LLM dump, skipped in every mode. These are
# either unambiguous tool directories or generated/compiled artefacts.
ALWAYS_SKIP_PATTERNS = [
    ".git/", ".hg/", ".svn/", "CVS/",
    "node_modules/", "bower_components/", "jspm_packages/",
    "__pycache__/", ".venv/", "venv/", ".mypy_cache/", ".pytest_cache/",
    ".ruff_cache/", ".tox/", ".nox/", ".eggs/", "*.egg-info/",
    ".idea/", ".vscode/", ".vs/",
    ".DS_Store", "Thumbs.db", "desktop.ini",
    "*.pyc", "*.pyo", "*.pyd", "*.class", "*.o", "*.obj",
    "*.a", "*.so", "*.dylib", "*.dll", "*.exe",
    "*.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Cargo.lock", "composer.lock", "Gemfile.lock", "uv.lock",
    "*.min.js", "*.min.css", "*.map",
]

# Generic directory names that are usually build output but could be real
# source. Skipped only when NOT relying on git (git mode already honours
# .gitignore, and if these are tracked it is probably deliberate).
WALK_ONLY_SKIP_PATTERNS = [
    "dist/", "build/", "out/", ".next/", ".nuxt/", ".svelte-kit/",
    ".cache/", ".parcel-cache/", "coverage/", ".nyc_output/", "htmlcov/",
    "target/", "*.log",
]

# --------------------------------------------------------------------------- #
# Content-based secret scanning                                              #
# --------------------------------------------------------------------------- #

SECRET_CONTENT_PATTERNS = [
    ("private key block", re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("AWS secret access key", re.compile(
        r"(?i)aws_secret_access_key\s*[=:]\s*\S{16,}")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("GitHub fine-grained PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Stripe secret key", re.compile(r"\b[rs]k_live_[A-Za-z0-9]{20,}\b")),
    ("generic secret assignment", re.compile(
        r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token"
        r"|client[_-]?secret|password|passwd)\b\s*[=:]\s*"
        r"""['"][^'"\s]{8,}['"]""")),
]

REDACTION_MARKER = "[REDACTED SECRET]"

# --------------------------------------------------------------------------- #
# Syntax-highlight hints                                                     #
# --------------------------------------------------------------------------- #

LANG_BY_EXT = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "tsx", ".jsx": "jsx",
    ".json": "json", ".jsonc": "jsonc", ".sh": "bash", ".bash": "bash",
    ".zsh": "bash", ".fish": "fish", ".ps1": "powershell", ".psm1": "powershell",
    ".bat": "batch", ".cmd": "batch", ".rb": "ruby", ".go": "go", ".rs": "rust",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".scala": "scala",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cxx": "cpp", ".cc": "cpp",
    ".hpp": "cpp", ".hh": "cpp", ".cs": "csharp", ".php": "php",
    ".swift": "swift", ".m": "objectivec", ".mm": "objectivec", ".pl": "perl",
    ".pm": "perl", ".lua": "lua", ".r": "r", ".jl": "julia", ".dart": "dart",
    ".ex": "elixir", ".exs": "elixir", ".erl": "erlang", ".clj": "clojure",
    ".hs": "haskell", ".ml": "ocaml", ".fs": "fsharp", ".nim": "nim",
    ".zig": "zig", ".sql": "sql", ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "scss", ".sass": "sass", ".less": "less",
    ".xml": "xml", ".svg": "xml", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini", ".conf": "ini",
    ".properties": "properties", ".md": "markdown", ".markdown": "markdown",
    ".rst": "rst", ".tex": "latex", ".mk": "makefile", ".gradle": "groovy",
    ".groovy": "groovy", ".vue": "vue", ".svelte": "svelte",
    ".proto": "protobuf", ".graphql": "graphql", ".gql": "graphql",
    ".tf": "hcl", ".hcl": "hcl", ".csv": "csv", ".tsv": "tsv", ".txt": "text",
    ".gitignore": "gitignore", ".dockerignore": "gitignore", ".env": "dotenv",
}
LANG_BY_NAME = {
    "Dockerfile": "dockerfile", "Containerfile": "dockerfile",
    "Makefile": "makefile", "GNUmakefile": "makefile", "Rakefile": "ruby",
    "Gemfile": "ruby", "Vagrantfile": "ruby", "Brewfile": "ruby",
    "CMakeLists.txt": "cmake", "Jenkinsfile": "groovy", "Procfile": "text",
    ".gitignore": "gitignore", ".dockerignore": "gitignore",
    ".gitattributes": "gitattributes", ".editorconfig": "ini",
    ".bashrc": "bash", ".zshrc": "bash", ".bash_profile": "bash",
}

MANIFEST_NAMES = [
    "package.json", "pyproject.toml", "requirements.txt", "requirements.in",
    "setup.py", "setup.cfg", "Pipfile", "go.mod", "Cargo.toml", "Gemfile",
    "pom.xml", "build.gradle", "build.gradle.kts", "composer.json",
    "pubspec.yaml", "mix.exs", "build.sbt", "Package.swift",
]

DOC_EXTS = (".md", ".markdown", ".rst", ".txt", ".adoc")


# --------------------------------------------------------------------------- #
# Glob matching (a practical subset of .gitignore semantics)                 #
# --------------------------------------------------------------------------- #

def _glob_to_re(pat: str) -> re.Pattern[str]:
    """Translate a shell glob to a regex anchored at the end.

    ``*`` matches within a path segment, ``**`` crosses ``/``, ``?`` matches one
    non-slash character, and ``[...]`` classes are passed through.
    """
    i, n = 0, len(pat)
    out = []
    while i < n:
        c = pat[i]
        i += 1
        if c == "*":
            if i < n and pat[i] == "*":
                i += 1
                if i < n and pat[i] == "/":
                    i += 1
                    out.append("(?:[^/]+/)*")
                else:
                    out.append(".*")
            else:
                out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = i
            if j < n and pat[j] in "!^":
                j += 1
            if j < n and pat[j] == "]":
                j += 1
            while j < n and pat[j] != "]":
                j += 1
            if j >= n:
                out.append(r"\[")
            else:
                inner = pat[i:j]
                i = j + 1
                if inner.startswith(("!", "^")):
                    inner = "^" + inner[1:]
                out.append("[" + inner + "]")
        else:
            out.append(re.escape(c))
    return re.compile("".join(out) + r"\Z")


class Matcher:
    """Match POSIX-style relative paths against a list of glob patterns."""

    def __init__(self, patterns):
        self._rules = []  # (negated, regex)
        for raw in patterns:
            pat = raw.strip()
            if not pat or pat.startswith("#"):
                continue
            negated = pat.startswith("!")
            if negated:
                pat = pat[1:]
            dir_only = pat.endswith("/")
            pat = pat.rstrip("/")
            anchored = pat.startswith("/")
            pat = pat.lstrip("/")
            if not pat:
                continue
            if "/" in pat and anchored:
                bases = [pat]
            elif "/" in pat:
                bases = [pat, "**/" + pat]
            else:
                bases = [pat, "**/" + pat]
            for base in bases:
                self._rules.append((negated, _glob_to_re(base)))
                # A directory match also covers everything beneath it.
                self._rules.append((negated, _glob_to_re(base + "/**")))
            if dir_only:
                # keep only the "and everything beneath" rules meaningful;
                # the bare match above is harmless for our file-only inputs
                pass

    def __bool__(self):
        return bool(self._rules)

    def match(self, relpath: str) -> bool:
        matched = False
        for negated, rx in self._rules:
            if rx.match(relpath):
                matched = not negated
        return matched


# --------------------------------------------------------------------------- #
# File discovery                                                             #
# --------------------------------------------------------------------------- #

def _run_git(root: Path, *args):
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return proc.stdout


def is_git_repo(root: Path) -> bool:
    out = _run_git(root, "rev-parse", "--is-inside-work-tree")
    return out is not None and out.strip() == b"true"


def git_list_files(root: Path):
    out = _run_git(
        root, "ls-files", "-z",
        "--cached", "--others", "--exclude-standard",
    )
    if out is None:
        return None
    seen = set()
    files = []
    for chunk in out.split(b"\x00"):
        if not chunk:
            continue
        rel = chunk.decode("utf-8", "surrogateescape")
        if rel not in seen:
            seen.add(rel)
            files.append(rel)
    return files


def walk_list_files(root: Path, prune: Matcher):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
        kept = []
        for d in sorted(dirnames):
            rel = d if not rel_dir else rel_dir + "/" + d
            if not prune.match(rel + "/"):
                kept.append(d)
        dirnames[:] = kept
        for f in sorted(filenames):
            rel = f if not rel_dir else rel_dir + "/" + f
            files.append(rel)
    return files


def collect_files(root: Path, use_git: bool, extra_exclude, includes):
    """Return (sorted relpaths, used_git)."""
    llmctxignore = []
    ig_path = root / ".llmctxignore"
    if ig_path.is_file():
        try:
            llmctxignore = ig_path.read_text("utf-8", errors="replace").splitlines()
        except OSError:
            llmctxignore = []

    secret_m = Matcher(SECRET_NAME_PATTERNS)
    always_m = Matcher(ALWAYS_SKIP_PATTERNS)
    walk_only_m = Matcher(WALK_ONLY_SKIP_PATTERNS)
    user_m = Matcher(list(llmctxignore) + list(extra_exclude))
    include_m = Matcher(includes)

    used_git = bool(use_git) and is_git_repo(root)
    raw = git_list_files(root) if used_git else None
    if raw is None:
        used_git = False
        prune = Matcher(SECRET_NAME_PATTERNS + ALWAYS_SKIP_PATTERNS
                        + WALK_ONLY_SKIP_PATTERNS
                        + list(llmctxignore) + list(extra_exclude))
        raw = walk_list_files(root, prune)

    result = []
    for rel in raw:
        if secret_m.match(rel):
            continue
        if always_m.match(rel):
            continue
        if not used_git and walk_only_m.match(rel):
            continue
        if user_m and user_m.match(rel):
            continue
        if include_m and not include_m.match(rel):
            continue
        if not (root / rel).is_file():
            continue
        result.append(rel)
    result.sort(key=str.lower)
    return result, used_git


# --------------------------------------------------------------------------- #
# File reading & classification                                             #
# --------------------------------------------------------------------------- #

_TEXT_BYTES = bytes(range(0x20, 0x7F)) + b"\n\r\t\f\b\x1b"


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            chunk = fh.read(8192)
    except OSError:
        return True
    if not chunk:
        return False
    if b"\x00" in chunk:
        return True
    try:
        chunk.decode("utf-8")
        return False
    except UnicodeDecodeError:
        pass
    nontext = sum(byte not in _TEXT_BYTES for byte in chunk)
    return nontext / len(chunk) > 0.30


def lang_for(rel: str) -> str:
    name = rel.rsplit("/", 1)[-1]
    if name in LANG_BY_NAME:
        return LANG_BY_NAME[name]
    ext = os.path.splitext(name)[1].lower()
    if ext in LANG_BY_EXT:
        return LANG_BY_EXT[ext]
    if not ext and name.lower().startswith("dockerfile"):
        return "dockerfile"
    return "text"


def read_text(path: Path, max_bytes: int):
    """Return (text, truncated_bool, original_size)."""
    size = path.stat().st_size
    with path.open("rb") as fh:
        if max_bytes and size > max_bytes:
            data = fh.read(max_bytes)
            text = data.decode("utf-8", errors="replace")
            return text, True, size
        data = fh.read()
    return data.decode("utf-8", errors="replace"), False, size


def count_lines(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def fence_for(text: str) -> str:
    longest = 0
    for run in re.finditer(r"`+", text):
        longest = max(longest, len(run.group()))
    return "`" * max(3, longest + 1)


def scan_secrets(rel: str, text: str):
    """Return list of (lineno, label) for lines that look secret-bearing."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for label, rx in SECRET_CONTENT_PATTERNS:
            if rx.search(line):
                hits.append((lineno, label))
                break
    return hits


def redact(text: str) -> tuple[str, int]:
    out = []
    n = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        if any(rx.search(stripped) for _, rx in SECRET_CONTENT_PATTERNS):
            indent = line[: len(line) - len(line.lstrip())]
            eol = "\n" if line.endswith("\n") else ""
            out.append(indent + "# " + REDACTION_MARKER + eol)
            n += 1
        else:
            out.append(line)
    return "".join(out), n


# --------------------------------------------------------------------------- #
# Tree rendering                                                             #
# --------------------------------------------------------------------------- #

def render_tree(relpaths, root_label: str) -> str:
    root: dict = {}
    for rel in relpaths:
        node = root
        for part in rel.split("/"):
            node = node.setdefault(part, {})
    lines = [root_label.rstrip("/") + "/"]

    def walk(node: dict, prefix: str):
        items = sorted(node.items(), key=lambda kv: kv[0].lower())
        for idx, (name, child) in enumerate(items):
            last = idx == len(items) - 1
            branch = "└── " if last else "├── "
            lines.append(prefix + branch + name + ("/" if child else ""))
            if child:
                walk(child, prefix + ("    " if last else "│   "))

    walk(root, "")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Git summary                                                                #
# --------------------------------------------------------------------------- #

def git_summary(root: Path):
    def g(*args):
        out = _run_git(root, *args)
        if out is None:
            return ""
        return out.decode("utf-8", "replace").strip()

    return {
        "branch": g("rev-parse", "--abbrev-ref", "HEAD"),
        "remote": g("remote", "get-url", "origin"),
        "commits": g("log", "-15", "--date=short",
                     "--pretty=format:%h %ad %s"),
        "status": g("status", "--short"),
    }


# --------------------------------------------------------------------------- #
# Document assembly                                                          #
# --------------------------------------------------------------------------- #

def human_kb(nbytes: int) -> str:
    return f"{nbytes / 1024:,.1f} KB"


def build_document(root: Path, out_abs: Path, args):
    files, used_git = collect_files(
        root, use_git=not args.no_git,
        extra_exclude=args.exclude, includes=args.include,
    )

    entries = []       # (rel, lang, text, lines, truncated, orig_size)
    skipped_binary = []
    secret_hits = []   # (rel, lineno, label)
    redacted_files = []

    for rel in files:
        path = root / rel
        try:
            if path.resolve() == out_abs:
                continue
        except OSError:
            pass
        if is_binary(path):
            skipped_binary.append(rel)
            continue
        try:
            text, truncated, orig = read_text(path, args.max_bytes)
        except OSError:
            continue
        for lineno, label in scan_secrets(rel, text):
            secret_hits.append((rel, lineno, label))
        if args.redact:
            text, n = redact(text)
            if n:
                redacted_files.append((rel, n))
        entries.append((rel, lang_for(rel), text, count_lines(text),
                        truncated, orig))

    # -- Overview stats --
    total_lines = sum(e[3] for e in entries)
    total_bytes = sum(len(e[2].encode("utf-8")) for e in entries)
    lang_counts: dict = {}
    for entry in entries:
        lang_counts[entry[1]] = lang_counts.get(entry[1], 0) + 1
    lang_str = ", ".join(
        f"{k} ({v})"
        for k, v in sorted(lang_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )

    project = root.name or str(root)
    md = []
    md.append(f"# Project context: {project}")
    md.append("")
    md.append(f"_Generated by llmctx v{VERSION}. Review before sharing — the secret "
              "filter is a heuristic, not a guarantee._")
    md.append("")

    md.append("## Overview")
    md.append("")
    md.append("- Files: {} ({} lines, {})".format(
        len(entries), format(total_lines, ","), human_kb(total_bytes)))
    if lang_str:
        md.append(f"- Languages: {lang_str}")
    md.append("- File selection: {}".format(
        "git (`git ls-files`, honours .gitignore)" if used_git
        else "directory walk with built-in ignore list"))
    # token estimate filled in after the body is known (placeholder index)
    token_line_idx = len(md)
    md.append("")  # replaced with the estimate line once the body is built
    md.append("")

    # -- Manifests --
    manifests = [e for e in entries if e[0] in MANIFEST_NAMES]
    for rel, lang, text, *_ in manifests:
        md.append(f"### Manifest: `{rel}`")
        md.append("")
        fence = fence_for(text)
        md.append(fence + lang)
        md.append(text.rstrip("\n"))
        md.append(fence)
        md.append("")

    # -- Git --
    if used_git and not args.no_git:
        info = git_summary(root)
        md.append("## Git")
        md.append("")
        if info["branch"]:
            md.append("- Branch: `{}`".format(info["branch"]))
        if info["remote"]:
            md.append("- Remote: `{}`".format(info["remote"]))
        md.append("")
        if info["commits"]:
            md.append("### Recent commits")
            md.append("")
            md.append("```")
            md.append(info["commits"])
            md.append("```")
            md.append("")
        if info["status"]:
            md.append("### Working tree status")
            md.append("")
            md.append("```")
            md.append(info["status"])
            md.append("```")
            md.append("")

    # -- Structure --
    md.append("## Structure")
    md.append("")
    md.append("```")
    md.append(render_tree([e[0] for e in entries], project))
    md.append("```")
    md.append("")

    # -- Contents --
    ordered = sorted(entries, key=_content_sort_key)
    md.append("## Contents")
    md.append("")
    for i, (rel, _lang, _text, lines, truncated, _orig) in enumerate(ordered, 1):
        note = " _(truncated)_" if truncated else ""
        md.append(f"{i}. `{rel}` — {lines} lines{note}")
    md.append("")

    for rel, lang, text, _lines, truncated, orig in ordered:
        md.append(f"### `{rel}`")
        md.append("")
        redacted_n = dict(redacted_files).get(rel)
        if redacted_n:
            md.append(f"> ⚠️ {redacted_n} line(s) redacted (possible secrets).")
            md.append("")
        fence = fence_for(text)
        md.append(fence + lang)
        body = text.rstrip("\n")
        if truncated:
            shown = len(text.encode("utf-8"))
            body += ("\n\n... [truncated by --max-bytes: {} of {} bytes shown] ..."
                     .format(format(shown, ","), format(orig, ",")))
        md.append(body)
        md.append(fence)
        md.append("")

    document = "\n".join(md).rstrip("\n") + "\n"
    tokens = round(len(document) / 4)
    md[token_line_idx] = "- Estimated size: ~{} tokens (~{})".format(
        format(tokens, ","), human_kb(len(document.encode("utf-8"))))
    document = "\n".join(md).rstrip("\n") + "\n"

    stats = {
        "files": len(entries),
        "tokens": tokens,
        "bytes": len(document.encode("utf-8")),
        "skipped_binary": skipped_binary,
        "secret_hits": secret_hits,
        "used_git": used_git,
    }
    return document, stats


def _content_sort_key(entry):
    rel = entry[0]
    lower = rel.lower()
    name = lower.rsplit("/", 1)[-1]
    is_doc = (
        name.startswith("readme")
        or lower.endswith(DOC_EXTS)
        or lower.startswith("docs/")
        or "/docs/" in lower
    )
    return (0 if is_doc else 1, lower)


# --------------------------------------------------------------------------- #
# CLI                                                                        #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llmctx",
        description="Collect a project directory into one Markdown file for LLMs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 llmctx.py                    # current dir -> context.md\n"
            "  python3 llmctx.py ~/dev/app app.md   # a project -> app.md\n"
            "  python3 llmctx.py . --exclude 'tests/**' --redact\n"
        ),
    )
    p.add_argument("directory", nargs="?", default=".",
                   help="project directory (default: current directory)")
    p.add_argument("output", nargs="?", default=DEFAULT_OUTPUT,
                   help="output Markdown file (default: %(default)s)")
    p.add_argument("--max-bytes", type=int, default=0, metavar="N",
                   help="truncate files larger than N bytes (default: no limit)")
    p.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                   help="exclude paths matching GLOB (repeatable)")
    p.add_argument("--include", action="append", default=[], metavar="GLOB",
                   help="include only paths matching GLOB (repeatable)")
    p.add_argument("--redact", action="store_true",
                   help="replace lines that look like secrets with a marker")
    p.add_argument("--no-git", action="store_true",
                   help="ignore git; always walk the directory tree")
    p.add_argument("--version", action="version",
                   version=f"llmctx {VERSION}")
    return p


def _log(message: str) -> None:
    """Write an ASCII-safe status line to stderr (Windows consoles are cp125x)."""
    stream = sys.stderr
    try:
        enc = stream.encoding or "ascii"
        message.encode(enc)
    except (UnicodeEncodeError, LookupError):
        message = message.encode("ascii", "replace").decode("ascii")
    print(message, file=stream)


def _display_path(out_path: Path) -> str:
    try:
        return os.path.relpath(out_path, Path.cwd())
    except ValueError:  # different drive on Windows
        return str(out_path)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    root = Path(args.directory)
    if not root.is_dir():
        _log(f"llmctx: error: not a directory: {args.directory}")
        return 1
    root = root.resolve()

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_abs = out_path.resolve() if out_path.exists() else out_path

    document, stats = build_document(root, out_abs, args)
    # write_bytes keeps "\n" endings on every platform and every Python 3.8+
    # (Path.write_text gained the newline= argument only in 3.10).
    out_path.write_bytes(document.encode("utf-8"))

    _log("llmctx: wrote {} - {} files, ~{} tokens ({})".format(
        _display_path(out_path), stats["files"], format(stats["tokens"], ","),
        human_kb(stats["bytes"])))
    if stats["skipped_binary"]:
        _log("llmctx: skipped {} binary file(s)".format(
            len(stats["skipped_binary"])))
    seen = set()
    for rel, lineno, label in stats["secret_hits"]:
        key = (rel, label)
        if key in seen:
            continue
        seen.add(key)
        _log(f"llmctx: WARNING possible secret in {rel}:{lineno} ({label})")
    if stats["secret_hits"] and not args.redact:
        _log("llmctx: review the flagged files or re-run with --redact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
