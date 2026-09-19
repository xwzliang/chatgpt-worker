#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${1:-$PWD}"

json="$("$SCRIPT_DIR/discover.py" --project "$PROJECT" --json)" || {
  echo "$json"
  exit 1
}

python3 - "$json" "$SCRIPT_DIR" <<'PY'
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

print()
print("Browser transport:")
import shutil, subprocess, os, pathlib, platform
browser=d.get("browser", {})
transport=browser.get("transport", "cdp")
browser_ready = True
print(f"  Mode:           {transport}")
print(f"  auto_allow:     {browser.get('auto_allow', False)}")

if transport == "manual":
    print("  Automation:     none (user sends the prepared wake-up message manually)")
else:
    node_path = shutil.which("node")
    if node_path:
        try:
            ver = subprocess.check_output(["node", "-v"], text=True).strip()
            print(f"  Node.js:        ✓ ({ver})")
        except Exception:
            print(f"  Node.js:        ✓ ({node_path})")
    else:
        print("  Node.js:        ✗ NOT FOUND (required for prompt preparation/CDP)")
        browser_ready = False

    devtools_found = False
    active_port_paths = [
        os.environ.get("CHROME_DEVTOOLS_PORT_FILE"),
        os.path.expanduser("~/Library/Application Support/Google/Chrome/DevToolsActivePort"),
        os.path.expanduser("~/.config/google-chrome/DevToolsActivePort"),
        os.path.expanduser("~/.config/chromium/DevToolsActivePort"),
    ]
    for p in active_port_paths:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    port = f.readline().strip()
                    print(f"  Chrome DevTools:✓ Active (port {port})")
                    devtools_found = True
                    break
            except Exception:
                pass
    if not devtools_found:
        print("  Chrome DevTools:✗ Not active")
        browser_ready = False

    if transport == "native":
        html=browser.get("uivision_autorun_html")
        candidates=[html] if html else []
        candidates += [
            os.path.expanduser("~/uivision/ui.vision.html"),
            os.path.expanduser("~/Desktop/uivision/ui.vision.html"),
        ]
        found=next((p for p in candidates if p and os.path.isfile(os.path.expanduser(p))), None)
        print(f"  UI.Vision HTML: {'✓ ' + found if found else '✗ NOT FOUND'}")
        if not found:
            browser_ready = False
        macro_name=browser.get('uivision_macro_name', 'ChatGPTClickSendExistingTab')
        macro_candidates=[
            os.path.expanduser(f"~/Desktop/uivision/macros/{macro_name}.json"),
            os.path.expanduser(f"~/uivision/macros/{macro_name}.json"),
        ]
        macro_path=next((p for p in macro_candidates if os.path.isfile(p)), None)
        print(f"  UI.Vision macro:{'✓ ' + macro_path if macro_path else '✗ ' + macro_name + ' not installed'}")
        if not macro_path:
            browser_ready = False
    elif platform.system() == "Darwin":
        script_dir = pathlib.Path(sys.argv[2])
        auto_allow_bin = script_dir / "auto_allow"
        auto_allow_enabled = bool(browser.get("auto_allow", False))
        is_running = False
        try:
            p = subprocess.run(["pgrep", "-f", "auto_allow"], stdout=subprocess.PIPE, text=True)
            is_running = p.returncode == 0 and bool(p.stdout.strip())
        except Exception:
            pass
        if not auto_allow_enabled:
            print("  auto_allow run: disabled by config")
        elif is_running:
            print("  auto_allow run: ✓ RUNNING")
        elif (script_dir / "auto_allow.sh").is_file():
            print("  auto_allow run: ✓ Will start automatically before send")
        else:
            print("  auto_allow run: ✗ launcher missing")
            browser_ready = False

ready = bool(d.get("origin_verified")) and bool(d.get("target_repo")) and browser_ready
print()
print("Status: READY" if ready else "Status: NOT READY")
sys.exit(0 if ready else 1)
PY
