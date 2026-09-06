# llmctx

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Dest1n640/llmctx/actions/workflows/ci.yml/badge.svg)](https://github.com/Dest1n640/llmctx/actions/workflows/ci.yml)

Collect a whole project directory into a **single Markdown file** — a structure
tree plus the contents of every text file, with a short overview and a git
summary on top. Handy when you want to hand a small project to an LLM (or a
teammate) as one self-contained file.

Русская версия: [README.ru.md](README.ru.md).

## Quick start

One file, no dependencies. Pick your OS:

**macOS / Linux**

```bash
curl -O https://raw.githubusercontent.com/Dest1n640/llmctx/main/llmctx.py
python3 llmctx.py                 # scans the current directory -> context.md
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/Dest1n640/llmctx/main/llmctx.py -OutFile llmctx.py
python llmctx.py                  # scans the current directory -> context.md
```

Needs Python 3.8+ — install it from [python.org](https://www.python.org/downloads/)
or the Microsoft Store. `llmctx.ps1` is a thin wrapper if you prefer
`.\llmctx.ps1`.

**No Python? (macOS / Linux only)**

```bash
curl -O https://raw.githubusercontent.com/Dest1n640/llmctx/main/generate_context.sh
bash generate_context.sh .
```

`generate_context.sh` is a no-frills fallback: tree + file contents + name-based
filtering, nothing else. `llmctx.py` is the canonical, full-featured version.

## Usage

```
python3 llmctx.py [DIRECTORY] [OUTPUT.md] [options]
```

| Argument / option | Meaning |
| --- | --- |
| `DIRECTORY` | Project directory to scan (default: current directory) |
| `OUTPUT.md` | Output file (default: `context.md`) |
| `--max-bytes N` | Truncate files larger than `N` bytes (default: no limit) |
| `--exclude GLOB` | Skip paths matching `GLOB` (repeatable) |
| `--include GLOB` | Keep **only** paths matching `GLOB` (repeatable) |
| `--redact` | Replace lines that look like secrets with a marker |
| `--no-git` | Ignore git; always walk the directory tree |

```bash
python3 llmctx.py ~/dev/app app.md
python3 llmctx.py . --exclude 'tests/**' --exclude '*.snap'
python3 llmctx.py . --redact
```

## What ends up in the file

- **Overview** — detected languages, file / line / byte counts, a rough token
  estimate, and the contents of dependency manifests (`package.json`,
  `pyproject.toml`, `go.mod`, `Cargo.toml`, …).
- **Git** — current branch, remote, the last 15 commits and `git status`
  (only inside a git repository, unless `--no-git`).
- **Structure** — a real directory tree.
- **Contents** — a table of contents, then every text file in a fenced code
  block. Documentation (`README*`, `*.md`, `docs/`) comes first so the model
  reads intent before implementation.

Inside a git repository the file list comes from `git ls-files`, so your
`.gitignore` is honoured automatically. Otherwise `llmctx` walks the tree using
a built-in ignore list.

## What is excluded

- build junk and caches: `.git/`, `node_modules/`, `__pycache__/`, `.venv/`,
  `dist/`, `build/`, `*.log`, lock files, minified bundles, …
- likely secrets by name: `.env` / `.env.*`, `*.pem` / `*.key` / `*.pfx` /
  `*.p12`, `id_rsa` / `id_ed25519`, `.netrc`, `.pgpass`, `.npmrc`, `.pypirc`,
  `.aws/`, `.ssh/`, paths containing `credentials` or `secret.` / `secrets.`
- binary files (detected by content, no external tools)
- the output file itself

Add a `.llmctxignore` file next to your project (same glob syntax as
`.gitignore`) to extend the list, or pass `--exclude` for one-off runs.

## ⚠️ Secrets

The secret filter is a **heuristic, not a guarantee.** Name-based rules miss
oddly named files (`config.prod.json`, a `settings.py` with a key inside), and
the content scan only catches common key/token shapes. Flagged files are still
included — you get a warning on stderr; `--redact` blanks the matching lines.

**Review the generated file by eye** before you paste it into a chat, commit it,
or forward it.

## Limitations

- large files are included whole unless you pass `--max-bytes`;
- filtering is by path and by simple content patterns, not real secret
  detection;
- `--include` / `--exclude` use shell globs (`*` within a segment, `**` across
  `/`), a practical subset of `.gitignore` semantics.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```

The runtime (`llmctx.py`) stays dependency-free on purpose; `uv` and the dev
tools are only for working on the project.

## License

MIT — see [LICENSE](LICENSE).
