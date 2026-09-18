#!/usr/bin/env bash
# auto_allow.sh
# Unified launcher for Chrome remote debugging auto-approval on macOS.
# Automatically compiles auto_allow.swift if needed, or falls back to AppleScript.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$SCRIPT_DIR/auto_allow"
SWIFT_SRC="$SCRIPT_DIR/auto_allow.swift"
FALLBACK="$SCRIPT_DIR/auto-allow-chrome.sh"
PID_FILE="/tmp/chatgpt_worker_auto_allow.pid"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "auto_allow is only required and supported on macOS."
  exit 0
fi

status() {
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "auto_allow daemon is running (PID: $(cat "$PID_FILE"))"
    return 0
  elif pgrep -f "auto_allow" >/dev/null 2>&1; then
    local pids
    pids="$(pgrep -f "auto_allow" | tr '\n' ' ' | sed 's/ $//')"
    echo "auto_allow process detected running (PID: $pids)"
    return 0
  else
    echo "auto_allow daemon is not running."
    return 1
  fi
}

stop() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping auto_allow daemon (PID: $pid)..."
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi
  # Also kill any leftover auto_allow or auto-allow-chrome.sh processes
  pkill -f "auto_allow.swift" 2>/dev/null || true
  pkill -f "$SCRIPT_DIR/auto_allow" 2>/dev/null || true
  pkill -f "$FALLBACK" 2>/dev/null || true
  echo "auto_allow stopped."
}

build_if_needed() {
  if [[ -x "$BIN" ]]; then
    return 0
  fi
  if command -v swiftc >/dev/null 2>&1 && [[ -f "$SWIFT_SRC" ]]; then
    echo "Compiling native auto_allow daemon with swiftc..."
    swiftc -O "$SWIFT_SRC" -o "$BIN"
    chmod +x "$BIN"
    echo "Compiled successfully: $BIN"
    return 0
  fi
  return 1
}

run_foreground() {
  if build_if_needed && [[ -x "$BIN" ]]; then
    exec "$BIN"
  elif [[ -f "$FALLBACK" ]]; then
    echo "swiftc not found; falling back to AppleScript daemon: $FALLBACK"
    exec bash "$FALLBACK"
  else
    echo "Error: neither auto_allow binary nor fallback script could be run." >&2
    exit 1
  fi
}

start_daemon() {
  if status >/dev/null 2>&1; then
    echo "Daemon is already running."
    return 0
  fi

  if build_if_needed && [[ -x "$BIN" ]]; then
    nohup "$BIN" >/tmp/chatgpt_worker_auto_allow.log 2>&1 &
    echo $! > "$PID_FILE"
    echo "Started native auto_allow daemon (PID: $!). Log: /tmp/chatgpt_worker_auto_allow.log"
  elif [[ -f "$FALLBACK" ]]; then
    nohup bash "$FALLBACK" >/tmp/chatgpt_worker_auto_allow.log 2>&1 &
    echo $! > "$PID_FILE"
    echo "Started AppleScript auto_allow daemon (PID: $!). Log: /tmp/chatgpt_worker_auto_allow.log"
  fi
}

case "${1:-run}" in
  start|--daemon)
    start_daemon
    ;;
  stop)
    stop
    ;;
  status)
    status
    ;;
  compile)
    build_if_needed
    ;;
  run|foreground|*)
    run_foreground
    ;;
esac
