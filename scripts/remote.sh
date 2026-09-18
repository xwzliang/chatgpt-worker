#!/usr/bin/env bash
set -euo pipefail

HOST="${CHATGPT_WORKER_HOST:-ai-server}"

usage() {
  cat <<'USAGE'
Usage:
  remote.sh [--host HOST] exec COMMAND...
  remote.sh [--host HOST] repo REPO_PATH COMMAND...
  remote.sh [--host HOST] test REPO_PATH [TEST_COMMAND...]

Environment:
  CHATGPT_WORKER_HOST          SSH host/alias (default: ai-server)
  CHATGPT_WORKER_TEST_COMMAND Default test command used by test

Examples:
  remote.sh exec uname -a
  remote.sh repo /srv/myapp git status --short
  remote.sh test /srv/myapp 'pytest -q'
USAGE
}

if [[ "${1:-}" == "--host" ]]; then
  [[ $# -ge 3 ]] || { usage >&2; exit 2; }
  HOST="$2"
  shift 2
fi

MODE="${1:-}"
[[ -n "$MODE" ]] || { usage >&2; exit 2; }
shift

quote_args() {
  local out="" q
  for arg in "$@"; do
    printf -v q '%q' "$arg"
    out+="${out:+ }$q"
  done
  printf '%s' "$out"
}

case "$MODE" in
  exec)
    [[ $# -gt 0 ]] || { usage >&2; exit 2; }
    ssh "$HOST" -- "$(quote_args "$@")"
    ;;
  repo)
    [[ $# -ge 2 ]] || { usage >&2; exit 2; }
    repo_path="$1"; shift
    printf -v qrepo '%q' "$repo_path"
    ssh "$HOST" -- "cd $qrepo && $(quote_args "$@")"
    ;;
  test)
    [[ $# -ge 1 ]] || { usage >&2; exit 2; }
    repo_path="$1"; shift
    test_cmd="${*:-${CHATGPT_WORKER_TEST_COMMAND:-}}"
    [[ -n "$test_cmd" ]] || {
      echo "No test command supplied. Pass one or set CHATGPT_WORKER_TEST_COMMAND." >&2
      exit 2
    }
    printf -v qrepo '%q' "$repo_path"
    ssh "$HOST" -- "cd $qrepo && $test_cmd"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    usage >&2
    exit 2
    ;;
esac
