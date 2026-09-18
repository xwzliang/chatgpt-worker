#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

import discover

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROTOCOL = SCRIPT_DIR / "protocol.py"

def run(cmd: list[str], cwd: str | pathlib.Path | None = None, check: bool = True, capture: bool = True):
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and p.returncode != 0:
        stderr = (p.stderr or "").strip()
        raise RuntimeError(stderr or f"Command failed ({p.returncode}): {' '.join(cmd)}")
    return p

def git(repo: str | pathlib.Path, *args: str, check: bool = True):
    return run(["git", "-C", str(repo), *args], check=check)

def remote(host: str, script: str, check: bool = True):
    p = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, "bash -lc " + shlex.quote(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or f"Remote command failed on {host}")
    return p

def slug(value: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return s or "task"

def cache_root() -> pathlib.Path:
    return pathlib.Path(os.environ.get("CHATGPT_WORKER_CACHE", "~/.cache/chatgpt-worker")).expanduser()

def task_paths(info: dict[str, Any], task_slug: str):
    repo_slug = slug(info["origin"].replace("/", "__"))
    base = cache_root()
    return {
        "control": base / "control" / repo_slug / task_slug,
        "validation_local": base / "worktrees" / repo_slug / task_slug,
        "state": base / "tasks" / repo_slug / f"{task_slug}.json",
    }

def load_state(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"task state not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))

def save_state(path: pathlib.Path, data: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def origin_default_branch(repo: pathlib.Path) -> str:
    git(repo, "fetch", "origin")
    p = git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", check=False)
    if p.returncode == 0 and p.stdout.strip().startswith("origin/"):
        return p.stdout.strip().split("/", 1)[1]
    p = git(repo, "remote", "show", "origin")
    for line in p.stdout.splitlines():
        if "HEAD branch:" in line:
            return line.split(":", 1)[1].strip()
    for fallback in ("main", "master"):
        if git(repo, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{fallback}", check=False).returncode == 0:
            return fallback
    raise RuntimeError("unable to determine origin default branch")

def ensure_clean_control_worktree(source_repo: pathlib.Path, control: pathlib.Path, branch: str, base_branch: str):
    control.parent.mkdir(parents=True, exist_ok=True)
    git(source_repo, "worktree", "prune")

    if control.exists():
        if git(control, "rev-parse", "--is-inside-work-tree", check=False).returncode != 0:
            raise RuntimeError(f"control path exists but is not a Git worktree: {control}")
        current = git(control, "branch", "--show-current").stdout.strip()
        if current != branch:
            raise RuntimeError(f"existing control worktree is on {current!r}, expected {branch!r}")
        return

    remote_exists = git(source_repo, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}", check=False).returncode == 0
    local_exists = git(source_repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0
    if remote_exists:
        if local_exists:
            git(source_repo, "worktree", "add", str(control), branch)
            git(control, "reset", "--hard", f"origin/{branch}")
        else:
            git(source_repo, "worktree", "add", "-b", branch, str(control), f"origin/{branch}")
    elif local_exists:
        git(source_repo, "worktree", "add", str(control), branch)
    else:
        git(source_repo, "worktree", "add", "-b", branch, str(control), f"origin/{base_branch}")

def commit_and_push(repo: pathlib.Path, branch: str, message: str):
    status = git(repo, "status", "--porcelain").stdout.strip()
    if not status:
        return git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
    git(repo, "push", "-u", "origin", branch)
    return git(repo, "rev-parse", "HEAD").stdout.strip()

def protocol_cmd(control: pathlib.Path, *args: str, check: bool = True):
    return run([sys.executable, str(PROTOCOL), *args, "--repo", str(control)], check=check)

def start(args):
    info = discover.discover(args.project)
    if not info.get("origin_verified") or not info.get("target_repo"):
        raise RuntimeError("project discovery is not READY")

    task_slug = slug(args.task_slug or args.task)
    branch = args.branch or f"{info['branch_prefix']}{task_slug}"
    if not branch.startswith(info["branch_prefix"]):
        raise RuntimeError(f"task branch must start with configured branch_prefix {info['branch_prefix']!r}")
    paths = task_paths(info, task_slug)
    source_repo = pathlib.Path(info["project_root"])
    base_branch = origin_default_branch(source_repo)
    ensure_clean_control_worktree(source_repo, paths["control"], branch, base_branch)

    # Never overwrite unrelated dirty work in a reused control worktree.
    dirty = git(paths["control"], "status", "--porcelain").stdout.strip()
    if dirty:
        raise RuntimeError(f"control worktree has uncommitted changes: {paths['control']}")

    session = protocol_cmd(
        paths["control"],
        "init-session",
        "--repository", info["origin"],
        "--branch", branch,
        "--task", args.task,
        "--max-iterations", str(info["max_iterations"]),
    ).stdout.strip()

    rid = protocol_cmd(
        paths["control"],
        "add-request",
        "--session-id", session,
        "--type", "implementation",
        "--body-file", args.request_file,
    ).stdout.strip()

    request_commit = commit_and_push(paths["control"], branch, f"chatgpt-worker: request {rid}")

    state = {
        "version": 1,
        "project_root": info["project_root"],
        "origin": info["origin"],
        "execution": info["execution"],
        "task_slug": task_slug,
        "task_branch": branch,
        "base_branch": base_branch,
        "session_id": session,
        "current_request": rid,
        "control_worktree": str(paths["control"]),
        "validation_worktree": None,
        "request_commit": request_commit,
        "last_implementation_commit": None,
        "implementation_commits": [],
        "target_host": info.get("target_host"),
        "target_repo": info.get("target_repo"),
        "validation_commands": info.get("validation_commands", []),
        "path_mappings": info.get("path_mappings", []),
    }
    save_state(paths["state"], state)
    print(json.dumps({"ok": True, "state_file": str(paths["state"]), **state}, indent=2))

def sync_control(state: dict[str, Any]):
    control = pathlib.Path(state["control_worktree"])
    branch = state["task_branch"]
    git(control, "fetch", "origin")
    # Control worktree should only contain pushed protocol changes from the host.
    dirty = git(control, "status", "--porcelain").stdout.strip()
    if dirty:
        raise RuntimeError(f"control worktree has uncommitted changes: {control}")
    git(control, "reset", "--hard", f"origin/{branch}")

def response(args):
    state_path = pathlib.Path(args.state_file).expanduser()
    state = load_state(state_path)
    sync_control(state)
    control = pathlib.Path(state["control_worktree"])
    p = protocol_cmd(
        control,
        "check-response",
        "--session-id", state["session_id"],
        "--request-id", state["current_request"],
        "--json",
        check=False,
    )
    if p.returncode not in {0, 2, 3}:
        raise RuntimeError((p.stderr or "").strip() or "response check failed")
    data = json.loads(p.stdout)
    branch_head = git(control, "rev-parse", f"origin/{state['task_branch']}").stdout.strip()
    request_commit = state.get("request_commit")
    if request_commit:
        if git(control, "merge-base", "--is-ancestor", request_commit, branch_head, check=False).returncode != 0:
            raise RuntimeError(f"request commit is not an ancestor of origin/{state['task_branch']}")
        if branch_head == request_commit and not data.get("ready"):
            print(json.dumps({"ok": True, "ready": False, "reason": "branch_has_not_advanced", "request_commit": request_commit}, indent=2))
            return
    if not data.get("ready"):
        print(json.dumps(data, indent=2))
        return
    if not data.get("ok"):
        raise RuntimeError("response file exists but failed protocol validation: " + "; ".join(data.get("errors", [])))
    resp = data["response"]
    if resp["status"] != "completed":
        print(json.dumps({"ok": True, "ready": True, "response": resp}, indent=2))
        return
    impl = resp["implementation_commit"]
    if git(control, "cat-file", "-e", f"{impl}^{{commit}}", check=False).returncode != 0:
        raise RuntimeError(f"implementation commit not found after fetch: {impl}")
    if git(control, "merge-base", "--is-ancestor", impl, f"origin/{state['task_branch']}", check=False).returncode != 0:
        raise RuntimeError(f"implementation commit is not reachable from origin/{state['task_branch']}: {impl}")
    state["last_implementation_commit"] = impl
    commits = state.setdefault("implementation_commits", [])
    if impl not in commits:
        commits.append(impl)
    save_state(state_path, state)
    print(json.dumps({"ok": True, "ready": True, "implementation_commit": impl, "response": resp}, indent=2))

def wait_response(args):
    state_path = pathlib.Path(args.state_file).expanduser()
    deadline = time.monotonic() + args.timeout
    while True:
        state = load_state(state_path)
        control = pathlib.Path(state["control_worktree"])
        sync_control(state)
        p = protocol_cmd(
            control,
            "check-response",
            "--session-id", state["session_id"],
            "--request-id", state["current_request"],
            "--json",
            check=False,
        )
        if p.returncode not in {0, 2, 3}:
            raise RuntimeError((p.stderr or "").strip() or "response check failed")
        data = json.loads(p.stdout)
        branch_head = git(control, "rev-parse", f"origin/{state['task_branch']}").stdout.strip()
        request_commit = state.get("request_commit")

        advanced = bool(request_commit and branch_head != request_commit)
        if request_commit and git(control, "merge-base", "--is-ancestor", request_commit, branch_head, check=False).returncode != 0:
            raise RuntimeError(f"request commit is not an ancestor of origin/{state['task_branch']}")

        if data.get("ready"):
            if not advanced:
                raise RuntimeError("response file is present but task branch has not advanced beyond the request commit")
            if not data.get("ok"):
                raise RuntimeError("response file exists but failed protocol validation: " + "; ".join(data.get("errors", [])))
            resp = data["response"]
            if resp.get("status") != "completed":
                print(json.dumps({"ok": True, "ready": True, "response": resp, "branch_head": branch_head}, indent=2))
                return
            impl = resp["implementation_commit"]
            if git(control, "cat-file", "-e", f"{impl}^{{commit}}", check=False).returncode != 0:
                raise RuntimeError(f"implementation commit not found after fetch: {impl}")
            if git(control, "merge-base", "--is-ancestor", impl, f"origin/{state['task_branch']}", check=False).returncode != 0:
                raise RuntimeError(f"implementation commit is not reachable from origin/{state['task_branch']}: {impl}")
            state["last_implementation_commit"] = impl
            commits = state.setdefault("implementation_commits", [])
            if impl not in commits:
                commits.append(impl)
            save_state(state_path, state)
            print(json.dumps({
                "ok": True,
                "ready": True,
                "finished": True,
                "implementation_commit": impl,
                "finish_message": resp.get("finish_message"),
                "branch_head": branch_head,
                "response": resp,
            }, indent=2))
            return

        if time.monotonic() >= deadline:
            print(json.dumps({
                "ok": True,
                "ready": False,
                "timed_out": True,
                "request_commit": request_commit,
                "branch_head": branch_head,
            }, indent=2))
            return
        time.sleep(args.interval)

def local_validation_worktree(state: dict[str, Any], impl: str) -> pathlib.Path:
    source = pathlib.Path(state["project_root"])
    paths = task_paths({"origin": state["origin"]}, state["task_slug"])
    target = paths["validation_local"]
    target.parent.mkdir(parents=True, exist_ok=True)
    git(source, "worktree", "prune")
    if target.exists():
        if git(target, "rev-parse", "--is-inside-work-tree", check=False).returncode != 0:
            raise RuntimeError(f"validation path exists but is not a Git worktree: {target}")
        git(target, "reset", "--hard", impl)
        git(target, "clean", "-fd")
    else:
        git(source, "worktree", "add", "--detach", str(target), impl)
    return target

def remote_validation_worktree(state: dict[str, Any], impl: str) -> str:
    host = state["target_host"]
    repo = state["target_repo"]
    if not host or not repo:
        raise RuntimeError("remote task state is missing target_host/target_repo")
    parent = str(pathlib.PurePosixPath(repo).parent)
    repo_name = pathlib.PurePosixPath(repo).name
    target = f"{parent}/.chatgpt-worker-worktrees/{repo_name}/{state['task_slug']}"
    script = f"""
set -euo pipefail
repo={shlex.quote(repo)}
wt={shlex.quote(target)}
impl={shlex.quote(impl)}
git -C "$repo" fetch origin
git -C "$repo" cat-file -e "$impl^{{commit}}"
git -C "$repo" worktree prune
mkdir -p "$(dirname "$wt")"
if [ -e "$wt" ]; then
  git -C "$wt" rev-parse --is-inside-work-tree >/dev/null
  git -C "$wt" reset --hard "$impl"
  git -C "$wt" clean -fd
else
  git -C "$repo" worktree add --detach "$wt" "$impl"
fi
printf '%s\n' "$wt"
"""
    p = remote(host, script)
    return p.stdout.strip().splitlines()[-1]

def prepare_validation(args):
    state_path = pathlib.Path(args.state_file).expanduser()
    state = load_state(state_path)
    impl = args.commit or state.get("last_implementation_commit")
    if not impl:
        raise RuntimeError("no implementation commit available; run response first or pass --commit")
    if state["execution"] == "local":
        wt = str(local_validation_worktree(state, impl))
    else:
        wt = remote_validation_worktree(state, impl)
    state["validation_worktree"] = wt
    state["last_implementation_commit"] = impl
    save_state(state_path, state)
    print(json.dumps({"ok": True, "execution": state["execution"], "worktree": wt, "commit": impl}, indent=2))

def validate(args):
    state_path = pathlib.Path(args.state_file).expanduser()
    state = load_state(state_path)
    impl = state.get("last_implementation_commit")
    if not impl:
        raise RuntimeError("no implementation commit available")
    if not state.get("validation_worktree"):
        prepare_validation(argparse.Namespace(state_file=str(state_path), commit=None))
        state = load_state(state_path)
    wt = state["validation_worktree"]
    commands = state.get("validation_commands", [])
    if not commands:
        print(json.dumps({"ok": True, "passed": True, "commit": impl, "results": [], "note": "no validation commands configured"}, indent=2))
        return
    results=[]
    passed=True
    for cmd in commands:
        if state["execution"] == "local":
            p=subprocess.run(["bash","-lc",cmd],cwd=wt,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        else:
            p=remote(state["target_host"], f"cd {shlex.quote(wt)} && {cmd}", check=False)
            # Normalize remote stderr into output for one diagnostic stream.
            if p.stderr:
                p.stdout=(p.stdout or "") + ("\n" if p.stdout else "") + p.stderr
        results.append({"command":cmd,"exit_code":p.returncode,"output":(p.stdout or "")[-12000:]})
        if p.returncode != 0:
            passed=False
            if not args.keep_going:
                break
    print(json.dumps({"ok": True, "passed": passed, "commit": impl, "worktree": wt, "results": results}, indent=2))
    if not passed:
        sys.exit(4)

def next_request(args):
    state_path=pathlib.Path(args.state_file).expanduser()
    state=load_state(state_path)
    control=pathlib.Path(state["control_worktree"])
    sync_control(state)
    rid=protocol_cmd(
        control,
        "add-request",
        "--session-id", state["session_id"],
        "--type", args.type,
        "--body-file", args.request_file,
    ).stdout.strip()
    commit=commit_and_push(control,state["task_branch"],f"chatgpt-worker: request {rid}")
    state["current_request"]=rid
    state["request_commit"]=commit
    save_state(state_path,state)
    print(json.dumps({"ok":True,"request_id":rid,"request_commit":commit,"session_id":state["session_id"],"task_branch":state["task_branch"]},indent=2))

def prepare_delivery(args):
    state_path = pathlib.Path(args.state_file).expanduser()
    state = load_state(state_path)
    source = pathlib.Path(state["project_root"])
    commits = state.get("implementation_commits", [])
    if not commits:
        raise RuntimeError("no implementation commits recorded")

    delivery_branch = args.branch or f"{state['task_branch']}-delivery"
    if delivery_branch == state["task_branch"]:
        raise RuntimeError("delivery branch must differ from the audit/task branch")

    git(source, "fetch", "origin")
    base_ref = f"origin/{state['base_branch']}"
    paths = task_paths({"origin": state["origin"]}, state["task_slug"])
    delivery = cache_root() / "delivery" / slug(state["origin"].replace("/", "__")) / state["task_slug"]

    git(source, "worktree", "prune")
    if delivery.exists():
        git(source, "worktree", "remove", "--force", str(delivery), check=False)
    if git(source, "show-ref", "--verify", "--quiet", f"refs/heads/{delivery_branch}", check=False).returncode == 0:
        git(source, "branch", "-D", delivery_branch)
    git(source, "worktree", "add", "-b", delivery_branch, str(delivery), base_ref)

    try:
        for commit in commits:
            git(delivery, "cherry-pick", commit)
        # Communication runtime must never leak into the delivery branch.
        runtime = delivery / ".chatgpt-worker"
        if runtime.exists():
            shutil.rmtree(runtime)
            git(delivery, "add", "-A")
            if git(delivery, "status", "--porcelain").stdout.strip():
                git(delivery, "commit", "-m", "chatgpt-worker: exclude runtime communication from delivery")
        git(delivery, "push", "-u", "origin", delivery_branch)
        head = git(delivery, "rev-parse", "HEAD").stdout.strip()
    except Exception:
        git(delivery, "cherry-pick", "--abort", check=False)
        raise
    finally:
        git(source, "worktree", "remove", "--force", str(delivery), check=False)
        git(source, "worktree", "prune", check=False)

    state["delivery_branch"] = delivery_branch
    state["delivery_commit"] = head
    save_state(state_path, state)
    print(json.dumps({
        "ok": True,
        "delivery_branch": delivery_branch,
        "delivery_commit": head,
        "base_branch": state["base_branch"],
        "implementation_commits": commits,
        "communication_runtime_included": False,
    }, indent=2))

def finish(args):
    state_path=pathlib.Path(args.state_file).expanduser()
    state=load_state(state_path)
    control=pathlib.Path(state["control_worktree"])
    sync_control(state)
    protocol_cmd(
        control,
        "mark",
        "--session-id", state["session_id"],
        "--status", args.status,
        *(["--last-tested-commit", state["last_implementation_commit"]] if state.get("last_implementation_commit") else []),
    )
    commit_and_push(control,state["task_branch"],f"chatgpt-worker: {args.status} session")
    cleanup_worktrees(state)
    state["finished_status"]=args.status
    state["validation_worktree"]=None
    save_state(state_path,state)
    print(json.dumps({"ok":True,"status":args.status,"task_branch":state["task_branch"],"session_id":state["session_id"],"audit_branch_preserved":True},indent=2))

def cleanup_worktrees(state: dict[str, Any]):
    source=pathlib.Path(state["project_root"])
    control=pathlib.Path(state["control_worktree"])
    validation=state.get("validation_worktree")

    if state["execution"] == "local" and validation:
        v=pathlib.Path(validation)
        if v.exists():
            git(source,"worktree","remove","--force",str(v),check=False)
    elif state["execution"] == "remote" and validation:
        repo=state["target_repo"]
        host=state["target_host"]
        remote(host,f"git -C {shlex.quote(repo)} worktree remove --force {shlex.quote(validation)} || true; git -C {shlex.quote(repo)} worktree prune",check=False)

    if control.exists():
        git(source,"worktree","remove","--force",str(control),check=False)
    git(source,"worktree","prune",check=False)

def status(args):
    state_path = pathlib.Path(args.state_file).expanduser()
    state = load_state(state_path)
    result = dict(state)
    result["state_file"] = str(state_path)
    control = pathlib.Path(state.get("control_worktree", ""))
    result["control_worktree_exists"] = bool(control and control.exists())
    if state.get("execution") == "local":
        vw = state.get("validation_worktree")
        result["validation_worktree_exists"] = bool(vw and pathlib.Path(vw).exists())
    else:
        result["validation_worktree_exists"] = None
    print(json.dumps({"ok": True, **result}, indent=2))

def make_wakeup_message(state: dict[str, Any]) -> str:
    return (
        "Continue the chatgpt-worker task.\n\n"
        f"Repository: {state['origin']}\n"
        f"Branch: {state['task_branch']}\n"
        f"Session: {state['session_id']}\n"
        f"Next request: {state['current_request']}\n\n"
        "Read .chatgpt-worker/PROTOCOL.md and the pending request file in the repository.\n"
        "Make the requested code changes, commit and push them, then write the corresponding response JSON file.\n"
    )

def message(args):
    state_path = pathlib.Path(args.state_file).expanduser()
    state = load_state(state_path)
    msg = make_wakeup_message(state)
    if args.send:
        send_script = SCRIPT_DIR / "send_message.js"
        if not send_script.exists():
            raise RuntimeError(f"send_message script not found: {send_script}")
        cmd = ["node", str(send_script), msg]
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            err_msg = (p.stderr or p.stdout or "").strip()
            raise RuntimeError(f"Failed to send message via CDP ({p.returncode}):\n{err_msg}")
        print(json.dumps({
            "ok": True,
            "sent": True,
            "state_file": str(state_path),
            "message": msg,
            "output": p.stdout.strip()
        }, indent=2))
        return
    if args.raw:
        sys.stdout.write(msg)
        return
    print(json.dumps({
        "ok": True,
        "sent": False,
        "state_file": str(state_path),
        "message": msg
    }, indent=2))

def cleanup(args):
    state_path=pathlib.Path(args.state_file).expanduser()
    state=load_state(state_path)
    cleanup_worktrees(state)
    state["validation_worktree"]=None
    save_state(state_path,state)
    print(json.dumps({"ok":True,"task_branch_preserved":True,"state_file":str(state_path)},indent=2))

def main():
    p=argparse.ArgumentParser(description="Automatic chatgpt-worker task branch/worktree lifecycle")
    sub=p.add_subparsers(dest="cmd",required=True)

    s=sub.add_parser("start")
    s.add_argument("--project",default=".")
    s.add_argument("--task",required=True)
    s.add_argument("--task-slug")
    s.add_argument("--branch")
    s.add_argument("--request-file",required=True)
    s.set_defaults(func=start)

    r=sub.add_parser("response")
    r.add_argument("--state-file",required=True)
    r.set_defaults(func=response)

    wr=sub.add_parser("wait-response")
    wr.add_argument("--state-file",required=True)
    wr.add_argument("--interval",type=float,default=10.0)
    wr.add_argument("--timeout",type=float,default=1800.0)
    wr.set_defaults(func=wait_response)

    pv=sub.add_parser("prepare-validation")
    pv.add_argument("--state-file",required=True)
    pv.add_argument("--commit")
    pv.set_defaults(func=prepare_validation)

    v=sub.add_parser("validate")
    v.add_argument("--state-file",required=True)
    v.add_argument("--keep-going",action="store_true")
    v.set_defaults(func=validate)

    n=sub.add_parser("next-request")
    n.add_argument("--state-file",required=True)
    n.add_argument("--type",default="validation_failure",choices=["implementation","validation_failure","review_feedback","clarification"])
    n.add_argument("--request-file",required=True)
    n.set_defaults(func=next_request)

    d=sub.add_parser("prepare-delivery")
    d.add_argument("--state-file",required=True)
    d.add_argument("--branch")
    d.set_defaults(func=prepare_delivery)

    f=sub.add_parser("finish")
    f.add_argument("--state-file",required=True)
    f.add_argument("--status",default="completed",choices=["completed","failed","stopped"])
    f.set_defaults(func=finish)

    st=sub.add_parser("status")
    st.add_argument("--state-file",required=True)
    st.set_defaults(func=status)

    c=sub.add_parser("cleanup")
    c.add_argument("--state-file",required=True)
    c.set_defaults(func=cleanup)

    m=sub.add_parser("message")
    m.add_argument("--state-file",required=True)
    m.add_argument("--send",action="store_true",help="Send wake-up message directly to ChatGPT Web using send_message.js")
    m.add_argument("--raw",action="store_true",help="Print raw message text directly")
    m.set_defaults(func=message)

    args=p.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(json.dumps({"ok":False,"error":str(exc)},indent=2),file=sys.stderr)
        sys.exit(1)

if __name__=="__main__":
    main()
