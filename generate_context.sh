#!/bin/bash

set -euo pipefail

# Проверка аргументов
if [ -z "${1:-}" ]; then
    echo "Использование: $0 <путь_к_папке> [путь_к_выходному_файлу.md]"
    exit 1
fi

DIR="$1"
OUT_FILE="${2:-project_context.md}"

if [ ! -d "$DIR" ]; then
    echo "Ошибка: Директория '$DIR' не существует."
    exit 1
fi

echo "Генерация контекста из '$DIR' в файл '$OUT_FILE'..."

# Регулярное выражение для файлов и папок, которые нужно игнорировать.
# Первый блок — служебный мусор, добавляйте сюда свои форматы/папки (разделяя |).
# Второй блок — типовые секреты: они НЕ должны попадать в контекст.
IGNORE_PATTERN="(\.git/|node_modules/|__pycache__/|\.venv/|venv/|\.idea/|\.vscode/|\.DS_Store|\.log$|\.pyc$|\.lock$|package-lock\.json$|yarn\.lock$|(^|/)\.env(\.[^/]*)?$|\.pem$|\.key$|\.pfx$|\.p12$|(^|/)id_rsa|(^|/)id_ed25519|(^|/)\.pgpass$|(^|/)\.netrc$|(^|/)secrets?\.|(^|/)credentials|(^|/)\.aws/|(^|/)\.ssh/|(^|/)\.npmrc$|(^|/)\.pypirc$)"

# Абсолютные пути считаем до перехода в каталог проекта, чтобы затем
# исключить из обхода сам выходной файл (иначе он попадает в свой же дамп).
DIR_ABS="$(cd "$DIR" && pwd)"
mkdir -p "$(dirname "$OUT_FILE")"
: > "$OUT_FILE"
OUT_FILE_ABS="$(cd "$(dirname "$OUT_FILE")" && pwd)/$(basename "$OUT_FILE")"
PROJECT_NAME="$(basename "$DIR_ABS")"

cd "$DIR_ABS"

# --- Структура проекта ---
# find + sort — детерминированный порядок; sed рисует подобие дерева.
{
    echo "# Контекст проекта: $PROJECT_NAME"
    echo
    echo "## Структура проекта"
    echo '```text'
    find . -print | LC_ALL=C sort | { grep -vE "$IGNORE_PATTERN" || true; } \
        | sed -e 's;[^/]*/;|____;g;s;____|; |;g' || true
    echo '```'
    echo
    echo "## Содержимое файлов"
    echo
} >> "$OUT_FILE_ABS"

# --- Содержимое файлов ---
while IFS= read -r FILE; do
    REL="${FILE#./}"
    FILE_ABS="$DIR_ABS/$REL"

    # Не включаем в дамп сам выходной файл
    if [ "$FILE_ABS" = "$OUT_FILE_ABS" ]; then
        continue
    fi

    # Пропускаем бинарные файлы (картинки, скомпилированные бинарники и т.д.)
    if file --mime "$FILE" 2>/dev/null | grep -q 'charset=binary'; then
        echo "Пропущен бинарный файл: $REL"
        continue
    fi

    # Расширение — для подсветки синтаксиса в Markdown
    FILENAME="$(basename "$FILE")"
    EXT="${FILENAME##*.}"
    if [ "$FILENAME" = "$EXT" ]; then
        EXT="text" # Если расширения нет (например, Dockerfile)
    fi

    # Ограждение кода делаем длиннее самой длинной серии бэктиков в файле,
    # иначе файлы, содержащие ```, ломают разметку выходного Markdown.
    MAX_TICKS="$(grep -oE '`+' "$FILE" 2>/dev/null | awk '{ if (length > m) m = length } END { print m + 0 }' || true)"
    if [ "${MAX_TICKS:-0}" -ge 3 ]; then
        FENCE="$(printf "%$((MAX_TICKS + 1))s" '' | tr ' ' '`')"
    else
        FENCE='```'
    fi

    {
        echo "### \`$REL\`"
        printf '%s%s\n' "$FENCE" "$EXT"
        cat "$FILE" 2>/dev/null || true
        echo "$FENCE"
        echo
    } >> "$OUT_FILE_ABS"

done < <(find . -type f -print | LC_ALL=C sort | { grep -vE "$IGNORE_PATTERN" || true; })

echo "Готово! Результат сохранен в $OUT_FILE"
