#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.parse

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
SEND_SCRIPT = SCRIPT_DIR / "send_message.js"
DEFAULT_MACRO = "ChatGPTClickSendExistingTab"

def candidate_uivision_html(explicit: str | None) -> pathlib.Path:
    candidates = []
    if explicit:
        candidates.append(pathlib.Path(explicit).expanduser())
    env = os.environ.get("UIV_HTML") or os.environ.get("UIVISION_AUTORUN_HTML")
    if env:
        candidates.append(pathlib.Path(env).expanduser())
    candidates.extend([
        pathlib.Path("~/uivision/ui.vision.html").expanduser(),
        pathlib.Path("~/Desktop/uivision/ui.vision.html").expanduser(),
    ])
    for p in candidates:
        if p.is_file():
            return p.resolve()
    raise FileNotFoundError(
        "UI.Vision autorun HTML not found. Generate it in UI.Vision Settings > API > "
        "Create autorun HTML, then configure [browser].uivision_autorun_html or set UIV_HTML."
    )

def launch_url(url: str):
    if sys.platform == "darwin":
        # Using AppleScript to tell Google Chrome directly ensures query parameters
        # on file:// URLs are preserved and the UI.Vision extension executes immediately.
        # It also brings Chrome to the front for reliable native XClick execution.
        safe_url = url.replace("\\", "\\\\").replace('"', '\\"')
        script = f'''tell application "Google Chrome"
            activate
            open location "{safe_url}"
        end tell'''
        cmd = ["osascript", "-e", script]
    elif sys.platform.startswith("linux"):
        cmd = ["xdg-open", url]
    else:
        raise RuntimeError("native UI.Vision transport currently supports macOS/Linux launchers")
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "").strip() or "failed to launch UI.Vision autorun URL")

def wait_log(path: pathlib.Path, timeout: float):
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
            last = text
            low = text.lower()
            if "status=ok" in low or "macro completed" in low:
                return True, text
            if "status=error" in low or "macro failed" in low or "[error]" in low:
                return False, text
        time.sleep(0.5)
    return False, last

def main():
    p = argparse.ArgumentParser(description="Prepare ChatGPT message with CDP, then click Send via UI.Vision XClick.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--message")
    g.add_argument("--file")
    p.add_argument("--uivision-html")
    p.add_argument("--macro-name", default=DEFAULT_MACRO)
    p.add_argument("--timeout", type=float, default=60.0)
    args = p.parse_args()

    if args.file:
        msg = pathlib.Path(args.file).read_text(encoding="utf-8")
    else:
        msg = args.message
    if not msg or not msg.strip():
        raise SystemExit("message is empty")
    if not SEND_SCRIPT.is_file():
        raise SystemExit(f"send_message.js not found: {SEND_SCRIPT}")

    prep = subprocess.run(
        ["node", str(SEND_SCRIPT), "--prepare-only", msg],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if prep.returncode != 0:
        raise SystemExit((prep.stderr or prep.stdout or "").strip())

    uiv_html = candidate_uivision_html(args.uivision_html)
    log = pathlib.Path(tempfile.gettempdir()) / f"chatgpt-worker-uivision-{os.getpid()}.log"
    try:
        log.unlink(missing_ok=True)
    except TypeError:
        if log.exists():
            log.unlink()

    query = urllib.parse.urlencode({
        "direct": "1",
        "macro": args.macro_name,
        "closeRPA": "1",
        "savelog": str(log),
    })
    url = uiv_html.as_uri() + "?" + query
    launch_url(url)

    ok, text = wait_log(log, args.timeout)
    result = {
        "ok": ok,
        "prepared_with_cdp": True,
        "clicked_with_uivision": ok,
        "macro_name": args.macro_name,
        "uivision_html": str(uiv_html),
        "log_file": str(log),
        "log_tail": text[-4000:],
    }
    print(json.dumps(result, indent=2))
    if not ok:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
