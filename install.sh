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

chmod +x "$DEST/install.sh" "$DEST/scripts/"*.sh "$DEST/scripts/"*.py "$DEST/scripts/"*.js 2>/dev/null || true

# Compile native auto_allow daemon on macOS if swiftc is available
if [[ "$(uname -s)" == "Darwin" ]] && command -v swiftc >/dev/null 2>&1; then
  if [[ -f "$DEST/scripts/auto_allow.swift" ]]; then
    echo "Compiling native auto_allow daemon..."
    swiftc -O "$DEST/scripts/auto_allow.swift" -o "$DEST/scripts/auto_allow" 2>/dev/null || true
    chmod +x "$DEST/scripts/auto_allow" 2>/dev/null || true
  fi
fi

# Ensure global skills link for chatgpt-web-messenger
GLOBAL_SKILLS="$HOME/.gemini/config/skills"
if [[ -d "$DEST/skills/chatgpt-web-messenger" ]]; then
  mkdir -p "$GLOBAL_SKILLS"
  rm -rf "$GLOBAL_SKILLS/chatgpt-web-messenger"
  ln -s "$DEST/skills/chatgpt-web-messenger" "$GLOBAL_SKILLS/chatgpt-web-messenger" 2>/dev/null || cp -r "$DEST/skills/chatgpt-web-messenger" "$GLOBAL_SKILLS/"
fi

relaunch_antigravity_macos() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Automatic relaunch is currently implemented for macOS only."
    return 0
  fi

  local app_path=""
  local app_name=""

  if [[ -d "/Applications/Antigravity.app" ]]; then
    app_path="/Applications/Antigravity.app"
    app_name="Antigravity"
  elif [[ -d "/Applications/Antigravity IDE.app" ]]; then
    app_path="/Applications/Antigravity IDE.app"
    app_name="Antigravity IDE"
  else
    echo "Neither Antigravity.app nor Antigravity IDE.app was found in /Applications; skipping relaunch."
    return 0
  fi

  echo
  echo "Relaunching $app_name..."

  # Ask the installed app to quit cleanly first so open windows/state can be saved.
  osascript -e "tell application \"$app_name\" to quit" >/dev/null 2>&1 || true

  # Wait briefly for the Electron process tree to exit.
  for _ in {1..40}; do
    if ! pgrep -f "$app_path/Contents/" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done

  # Match cockpit-tools' macOS launch behavior: start a fresh LaunchServices instance.
  if open -n -a "$app_name"; then
    echo "$app_name relaunched."
  else
    echo "Plugin installed, but $app_name could not be relaunched automatically." >&2
    echo "Please launch $app_name manually." >&2
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
echo "  1. Add .chatgpt-worker.toml to each project (see examples/project-config-*.toml)."
echo "  2. For remote projects, configure the SSH alias in ~/.ssh/config."
echo "  3. From the opened project, run: $DEST/scripts/doctor.sh"
echo "  4. Invoke /chatgpt-worker or ask Antigravity to delegate a coding task to ChatGPT Web."
