#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

PROTOCOL_VERSION = 1

def load_json(path: pathlib.Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: pathlib.Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return value or "task"

def protocol_root(repo: pathlib.Path):
    return repo / ".chatgpt-worker"

def session_dir(repo: pathlib.Path, session_id: str):
    return protocol_root(repo) / "sessions" / session_id

def init_session(args):
    repo = pathlib.Path(args.repo).resolve()
    sid = args.session_id or f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{slugify(args.task)}"
    sdir = session_dir(repo, sid)
    if sdir.exists():
        raise RuntimeError(f"session already exists: {sdir}")
    (sdir / "requests").mkdir(parents=True)
    (sdir / "responses").mkdir(parents=True)
    state = {
        "protocol_version": PROTOCOL_VERSION,
        "session_id": sid,
        "repository": args.repository,
        "task_branch": args.branch,
        "status": "waiting_for_worker",
        "current_request": 0,
        "last_tested_commit": None,
        "max_iterations": args.max_iterations,
    }
    write_json(sdir / "session.json", state)
    print(sid)

def add_request(args):
    repo = pathlib.Path(args.repo).resolve()
    sdir = session_dir(repo, args.session_id)
    state_path = sdir / "session.json"
    state = load_json(state_path)
    n = int(state.get("current_request", 0)) + 1
    rid = f"{n:04d}"
    req = sdir / "requests" / f"{rid}.md"
    if req.exists():
        raise RuntimeError(f"request already exists: {req}")
    body = pathlib.Path(args.body_file).read_text(encoding="utf-8") if args.body_file else args.body
    response_rel = f".chatgpt-worker/sessions/{args.session_id}/responses/{rid}.json"
    text = (
        f"# Request {rid}\n\n"
        f"Type: `{args.type}`\n\n"
        f"{body.rstrip()}\n\n"
        "## Required completion\n\n"
        "When finished, commit and push the code changes and create this response file:\n\n"
        f"`{response_rel}`\n\n"
        "Follow `.chatgpt-worker/PROTOCOL.md`.\n"
    )
    req.write_text(text, encoding="utf-8")
    state["current_request"] = n
    state["status"] = "waiting_for_worker"
    write_json(state_path, state)
    print(rid)

def check_response(args):
    repo = pathlib.Path(args.repo).resolve()
    rid = f"{int(args.request_id):04d}"
    path = session_dir(repo, args.session_id) / "responses" / f"{rid}.json"
    if not path.exists():
        if args.json:
            print(json.dumps({"ok": True, "ready": False, "path": str(path)}))
        sys.exit(3)
    data = load_json(path)
    errors=[]
    if data.get("protocol_version") != PROTOCOL_VERSION:
        errors.append("unsupported protocol_version")
    if str(data.get("request_id")) != rid:
        errors.append("request_id mismatch")
    if data.get("status") not in {"completed","blocked","failed"}:
        errors.append("invalid status")
    if not isinstance(data.get("summary"), str) or not data.get("summary","").strip():
        errors.append("summary is required")
    if data.get("status") == "completed" and not isinstance(data.get("implementation_commit"), str):
        errors.append("implementation_commit is required for completed response")
    result={"ok": not errors, "ready": True, "path": str(path), "response": data, "errors": errors}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
    sys.exit(0 if not errors else 2)

def mark(args):
    repo=pathlib.Path(args.repo).resolve()
    path=session_dir(repo,args.session_id)/"session.json"
    state=load_json(path)
    state["status"]=args.status
    if args.last_tested_commit is not None:
        state["last_tested_commit"]=args.last_tested_commit
    write_json(path,state)

def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="cmd",required=True)

    s=sub.add_parser("init-session")
    s.add_argument("--repo",default=".")
    s.add_argument("--repository",required=True)
    s.add_argument("--branch",required=True)
    s.add_argument("--task",required=True)
    s.add_argument("--session-id")
    s.add_argument("--max-iterations",type=int,default=5)
    s.set_defaults(func=init_session)

    r=sub.add_parser("add-request")
    r.add_argument("--repo",default=".")
    r.add_argument("--session-id",required=True)
    r.add_argument("--type",default="implementation",choices=["implementation","validation_failure","review_feedback","clarification"])
    g=r.add_mutually_exclusive_group(required=True)
    g.add_argument("--body")
    g.add_argument("--body-file")
    r.set_defaults(func=add_request)

    c=sub.add_parser("check-response")
    c.add_argument("--repo",default=".")
    c.add_argument("--session-id",required=True)
    c.add_argument("--request-id",required=True)
    c.add_argument("--json",action="store_true")
    c.set_defaults(func=check_response)

    m=sub.add_parser("mark")
    m.add_argument("--repo",default=".")
    m.add_argument("--session-id",required=True)
    m.add_argument("--status",required=True,choices=["waiting_for_worker","waiting_for_orchestrator","completed","failed","stopped"])
    m.add_argument("--last-tested-commit")
    m.set_defaults(func=mark)

    args=p.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}",file=sys.stderr)
        sys.exit(1)

if __name__=="__main__":
    main()
