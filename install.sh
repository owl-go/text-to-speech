#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash install.sh [--target codex|claude|both] [--project DIRECTORY]

Default: install for Codex in ~/.agents/skills/text-to-speech.
--target claude installs in ~/.claude/skills/text-to-speech.
--target both installs for both tools.
--project DIRECTORY installs in that project's skill directories.
Run again to update; existing private voice files are preserved.
Requires Git and Python 3. Python dependencies and models load on first use.
EOF
}

args=(--target codex)
if [ "$#" -gt 0 ]; then
  args=("$@")
fi
while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --target)
      [ "$#" -ge 2 ] || { usage >&2; exit 2; }
      case "$2" in codex|claude|both) ;; *) usage >&2; exit 2 ;; esac
      shift 2 ;;
    --project)
      [ "$#" -ge 2 ] && [ -n "$2" ] || { usage >&2; exit 2; }
      shift 2 ;;
    *) usage >&2; exit 2 ;;
  esac
done

command -v git >/dev/null || { echo 'Git is required.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'Python 3 is required.' >&2; exit 1; }
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
echo 'Downloading text-to-speech skill...'
git clone --quiet --depth 1 --branch main https://github.com/owl-go/text-to-speech.git "$temporary/source"
python3 "$temporary/source/scripts/install_skill.py" --source "$temporary/source" "${args[@]}"
