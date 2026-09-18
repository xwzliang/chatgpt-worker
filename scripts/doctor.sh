#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${1:-$PWD}"

json="$("$SCRIPT_DIR/discover.py" --project "$PROJECT" --json)" || {
  echo "$json"
  exit 1
}

python3 - "$json" <<'PY'
import json, sys
d=json.loads(sys.argv[1])
print("ChatGPT Worker configuration")
print()
print(f"Project:          {d['project_root']}")
print(f"Config:           {d['config_path']}")
print(f"Git origin:       {d['origin']}")
print(f"Execution:        {d['execution']}")
if d["execution"] == "remote":
    print(f"Remote host:      {d['target_host']}")
    print("Repo roots:       " + ", ".join(d["repo_roots"]))
    if d.get("target_repo"):
        print(f"Remote repo:      {d['target_repo']}")
        if d.get("target_repo_local_mount"):
            print(f"Local mount:      {d['target_repo_local_mount']}")
        print("Origin match:     ✓")
    else:
        print("Remote repo:      NOT FOUND")
        print("Origin match:     ✗")
else:
    print(f"Local repo:       {d['target_repo']}")
    print("Origin match:     ✓")

maps=d.get("path_mappings", [])
if maps:
    print("Path mappings:")
    for item in maps:
        print(f"  {item['remote']} -> {item['local']}")
comm=d.get("communication", {})
if comm:
    print(f"Runtime dir:      {comm.get('runtime_dir', '.chatgpt-worker')}")
    print(f"Retain on merge:  {comm.get('retain_on_merge', False)}")
print(f"Branch prefix:    {d['branch_prefix']}")
print(f"Max iterations:   {d['max_iterations']}")
cmds=d.get("validation_commands", [])
print("Validation:")
if cmds:
    for cmd in cmds:
        print(f"  - {cmd}")
else:
    print("  (none configured)")

ready = bool(d.get("origin_verified")) and bool(d.get("target_repo"))
print()
print("Status: READY" if ready else "Status: NOT READY")
sys.exit(0 if ready else 1)
PY
