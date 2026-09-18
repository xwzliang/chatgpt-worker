#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME="chatgpt-worker"
REPO_URL="${CHATGPT_WORKER_REPO_URL:-https://github.com/xwzliang/chatgpt-worker.git}"
MODE="ide"
DEST=""

usage() {
  cat <<'USAGE'
Install or update chatgpt-worker for Google Antigravity.

Usage:
  bash install.sh [--ide|--cli] [--dest PATH]

Options:
  --ide       Install for the Antigravity IDE (default).
              Default: ~/.gemini/config/plugins/chatgpt-worker
  --cli       Install with agy plugin install for Antigravity CLI.
  --dest PATH Override the IDE destination directory.
  -h, --help  Show this help.

Environment:
  CHATGPT_WORKER_REPO_URL  Override the Git repository URL.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ide) MODE="ide"; shift ;;
    --cli) MODE="cli"; shift ;;
    --dest)
      [[ $# -ge 2 ]] || { echo "--dest requires a path" >&2; exit 2; }
      DEST="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

command -v git >/dev/null 2>&1 || { echo "git is required." >&2; exit 1; }

tmp="$(mktemp -d)"
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

git clone --depth 1 "$REPO_URL" "$tmp/plugin" >/dev/null

if [[ "$MODE" == "cli" ]]; then
  command -v agy >/dev/null 2>&1 || {
    echo "agy was not found in PATH. Install Antigravity CLI first, or use --ide." >&2
    exit 1
  }
  agy plugin install "$tmp/plugin"
  echo "Installed $PLUGIN_NAME for Antigravity CLI."
  exit 0
fi

if [[ -z "$DEST" ]]; then
  DEST="$HOME/.gemini/config/plugins/$PLUGIN_NAME"
fi

mkdir -p "$(dirname "$DEST")"

if [[ -d "$DEST/.git" ]]; then
  echo "Updating existing installation at $DEST ..."
  git -C "$DEST" remote set-url origin "$REPO_URL"
  git -C "$DEST" fetch --prune origin
  default_branch="$(git -C "$DEST" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##' || true)"
  if [[ -z "$default_branch" ]]; then
    default_branch="$(git -C "$DEST" remote show origin | sed -n '/HEAD branch/s/.*: //p')"
  fi
  [[ -n "$default_branch" ]] || default_branch="master"
  git -C "$DEST" checkout -q "$default_branch" 2>/dev/null || true
  git -C "$DEST" reset --hard "origin/$default_branch"
elif [[ -e "$DEST" ]]; then
  backup="${DEST}.backup.$(date +%Y%m%d%H%M%S)"
  echo "Existing non-Git installation found; moving it to $backup"
  mv "$DEST" "$backup"
  git clone "$REPO_URL" "$DEST" >/dev/null
else
  git clone "$REPO_URL" "$DEST" >/dev/null
fi

chmod +x "$DEST/install.sh" "$DEST/scripts/remote.sh" 2>/dev/null || true

echo
echo "Installed $PLUGIN_NAME for Antigravity IDE:"
echo "  $DEST"
echo
echo "Next steps:"
echo "  1. Configure ~/.ssh/config (see examples/ssh-config.example)."
echo "  2. Optionally export CHATGPT_WORKER_HOST=<ssh-alias>."
echo "  3. Restart/reload Antigravity if the plugin is not discovered immediately."
echo "  4. Invoke /chatgpt-worker or ask Antigravity to delegate a coding task to ChatGPT Web."
