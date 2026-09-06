# llmctx

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Dest1n640/llmctx/actions/workflows/ci.yml/badge.svg)](https://github.com/Dest1n640/llmctx/actions/workflows/ci.yml)

Собирает весь каталог проекта в **один Markdown-файл** — дерево структуры плюс
содержимое всех текстовых файлов, с кратким обзором и git-сводкой в начале.
Удобно, когда нужно отдать небольшой проект нейросети (или коллеге) одним
самодостаточным файлом.

English version: [README.md](README.md).

## Быстрый старт

Один файл, без зависимостей. Выбери свою ОС:

**macOS / Linux**

```bash
curl -O https://raw.githubusercontent.com/Dest1n640/llmctx/main/llmctx.py
python3 llmctx.py                 # сканирует текущий каталог -> context.md
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/Dest1n640/llmctx/main/llmctx.py -OutFile llmctx.py
python llmctx.py                  # сканирует текущий каталог -> context.md
```

Нужен Python 3.8+ — поставь с [python.org](https://www.python.org/downloads/) или
из Microsoft Store. `llmctx.ps1` — тонкая обёртка, если удобнее звать
`.\llmctx.ps1`.

**Без Python? (только macOS / Linux)**

```bash
curl -O https://raw.githubusercontent.com/Dest1n640/llmctx/main/generate_context.sh
bash generate_context.sh .
```

`generate_context.sh` — простой fallback: дерево + содержимое файлов +
фильтрация по именам, и всё. Канонична и функциональна Python-версия `llmctx.py`.

## Использование

```
python3 llmctx.py [КАТАЛОГ] [ВЫХОД.md] [опции]
```

| Аргумент / опция | Значение |
| --- | --- |
| `КАТАЛОГ` | Каталог проекта (по умолчанию — текущий) |
| `ВЫХОД.md` | Выходной файл (по умолчанию `context.md`) |
| `--max-bytes N` | Обрезать файлы больше `N` байт (по умолчанию без лимита) |
| `--exclude GLOB` | Пропускать пути по маске `GLOB` (можно повторять) |
| `--include GLOB` | Оставить **только** пути по маске `GLOB` (можно повторять) |
| `--redact` | Заменять строки, похожие на секреты, на маркер |
| `--no-git` | Игнорировать git, всегда обходить дерево каталога |

```bash
python3 llmctx.py ~/dev/app app.md
python3 llmctx.py . --exclude 'tests/**' --exclude '*.snap'
python3 llmctx.py . --redact
```

## Что попадает в файл

- **Overview** — определённые языки, число файлов / строк / байт, грубая оценка
  в токенах и содержимое манифестов зависимостей (`package.json`,
  `pyproject.toml`, `go.mod`, `Cargo.toml`, …).
- **Git** — текущая ветка, remote, последние 15 коммитов и `git status`
  (только внутри git-репозитория, если не задан `--no-git`).
- **Structure** — настоящее дерево каталога.
- **Contents** — оглавление, затем каждый текстовый файл в блоке кода.
  Документация (`README*`, `*.md`, `docs/`) идёт первой, чтобы модель сначала
  прочитала намерение, а потом реализацию.

Внутри git-репозитория список файлов берётся из `git ls-files`, то есть твой
`.gitignore` учитывается автоматически. Иначе `llmctx` обходит дерево со
встроенным списком исключений.

## Что исключается

- мусор сборки и кэши: `.git/`, `node_modules/`, `__pycache__/`, `.venv/`,
  `dist/`, `build/`, `*.log`, lock-файлы, минифицированные бандлы, …
- вероятные секреты по имени: `.env` / `.env.*`, `*.pem` / `*.key` / `*.pfx` /
  `*.p12`, `id_rsa` / `id_ed25519`, `.netrc`, `.pgpass`, `.npmrc`, `.pypirc`,
  `.aws/`, `.ssh/`, пути с `credentials` и `secret.` / `secrets.`
- бинарные файлы (определяются по содержимому, без внешних утилит)
- сам выходной файл

Положи рядом с проектом файл `.llmctxignore` (синтаксис масок как у
`.gitignore`), чтобы дополнить список, или используй `--exclude` для разовых
запусков.

## ⚠️ Секреты

Фильтр секретов — это **эвристика, а не гарантия.** Правила по именам не поймают
нестандартно названные файлы (`config.prod.json`, `settings.py` с ключом
внутри), а сканирование содержимого ловит только типовые формы ключей и токенов.
Найденные файлы всё равно включаются — в stderr выводится предупреждение;
`--redact` затирает совпавшие строки.

**Просматривай получившийся файл глазами** перед тем, как вставлять его в чат,
коммитить или пересылать.

## Ограничения

- большие файлы вставляются целиком, если не задан `--max-bytes`;
- фильтрация идёт по путям и простым паттернам содержимого, а не полноценным
  детектором секретов;
- `--include` / `--exclude` используют shell-маски (`*` внутри сегмента, `**`
  через `/`) — практическое подмножество семантики `.gitignore`.

## Разработка

```bash
uv sync
uv run pytest
uv run ruff check .
```

Рантайм (`llmctx.py`) намеренно без зависимостей; `uv` и dev-инструменты нужны
только для работы над самим проектом.

## Лицензия

MIT — см. [LICENSE](LICENSE).
