#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME="chatgpt-worker"
REPO_URL="${CHATGPT_WORKER_REPO_URL:-https://github.com/xwzliang/chatgpt-worker.git}"
MODE="ide"
DEST=""
RELAUNCH=1

usage() {
  cat <<'USAGE'
Install or update chatgpt-worker for Google Antigravity.

Usage:
  bash install.sh [--ide|--cli] [--dest PATH] [--no-relaunch]

Options:
  --ide          Install for the Antigravity IDE (default).
                 Default: ~/.gemini/config/plugins/chatgpt-worker
  --cli          Install with agy plugin install for Antigravity CLI.
  --dest PATH    Override the IDE destination directory.
  --no-relaunch  Do not relaunch Antigravity IDE after installation.
  -h, --help     Show this help.

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
    --no-relaunch) RELAUNCH=0; shift ;;
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

relaunch_antigravity_macos() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Automatic relaunch is currently implemented for macOS only."
    return 0
  fi

  if [[ ! -d "/Applications/Antigravity IDE.app" ]]; then
    echo "Antigravity IDE.app was not found in /Applications; skipping relaunch."
    return 0
  fi

  echo
  echo "Relaunching Antigravity IDE..."

  # Ask the app to quit cleanly first so open windows/state can be saved.
  osascript -e 'tell application "Antigravity IDE" to quit' >/dev/null 2>&1 || true

  # Wait briefly for the Electron process tree to exit.
  for _ in {1..40}; do
    if ! pgrep -f '/Applications/Antigravity IDE.app/Contents/' >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done

  # Match cockpit-tools' macOS launch behavior: start a fresh LaunchServices instance.
  if open -n -a "Antigravity IDE"; then
    echo "Antigravity IDE relaunched."
  else
    echo "Plugin installed, but Antigravity IDE could not be relaunched automatically." >&2
    echo "Please launch Antigravity IDE manually." >&2
  fi
}

echo
echo "Installed $PLUGIN_NAME for Antigravity IDE:"
echo "  $DEST"

if [[ "$RELAUNCH" -eq 1 ]]; then
  relaunch_antigravity_macos
fi

echo
echo "Next steps:"
echo "  1. Configure ~/.ssh/config (see examples/ssh-config.example)."
echo "  2. Optionally export CHATGPT_WORKER_HOST=<ssh-alias>."
echo "  3. Invoke /chatgpt-worker or ask Antigravity to delegate a coding task to ChatGPT Web."
