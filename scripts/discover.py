#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shlex
import subprocess
import sys
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:
    print("Python 3.11+ is required (tomllib is part of the standard library).", file=sys.stderr)
    sys.exit(2)

CONFIG_NAME = ".chatgpt-worker.toml"

def run(cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or f"Command failed: {' '.join(cmd)}")
    return p

def git_root(start: str) -> pathlib.Path:
    p = run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    return pathlib.Path(p.stdout.strip()).resolve()

def git_origin(repo: pathlib.Path) -> str:
    p = run(["git", "remote", "get-url", "origin"], cwd=str(repo))
    return p.stdout.strip()

def normalize_origin(url: str) -> str:
    value = url.strip().rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if value.startswith("git@") and ":" in value:
        host_path = value.split("@", 1)[1]
        _, path = host_path.split(":", 1)
        return path.strip("/")
    if value.startswith("ssh://") or value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        return parsed.path.strip("/")
    if value.startswith("github.com/"):
        return value.split("/", 1)[1]
    return value

def load_config(repo: pathlib.Path) -> tuple[pathlib.Path, dict]:
    path = repo / CONFIG_NAME
    if not path.is_file():
        raise FileNotFoundError(f"{CONFIG_NAME} not found at repository root: {repo}")
    with path.open("rb") as f:
        cfg = tomllib.load(f)
    return path, cfg

def remote_exec(host: str, script: str) -> subprocess.CompletedProcess:
    remote_command = "bash -lc " + shlex.quote(script)
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, remote_command],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

def candidate_remote_repos(host: str, roots: list[str], repo_name: str) -> list[str]:
    # Fast guesses first, then one-level Git repositories under each configured root.
    quoted_roots = " ".join(shlex.quote(r) for r in roots)
    qname = shlex.quote(repo_name)
    script = f'''
set -e
for root in {quoted_roots}; do
  [ -d "$root" ] || continue
  if [ -d "$root"/{qname}/.git ] || git -C "$root"/{qname} rev-parse --git-dir >/dev/null 2>&1; then
    printf '%s\n' "$root"/{qname}
  fi
  find "$root" -mindepth 1 -maxdepth 2 -type d -name .git -print 2>/dev/null \
    | sed 's#/.git$##'
done | awk '!seen[$0]++'
'''
    p = remote_exec(host, script)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or f"Unable to inspect remote roots on {host}")
    return [line.strip() for line in p.stdout.splitlines() if line.strip()]

def remote_origin(host: str, path: str) -> str | None:
    p = remote_exec(host, f"git -C {shlex.quote(path)} remote get-url origin")
    if p.returncode != 0:
        return None
    return p.stdout.strip()


def path_mappings(cfg: dict) -> list[dict]:
    remote = cfg.get("remote", {})
    items = remote.get("path_mappings", [])
    if not isinstance(items, list):
        raise ValueError("[remote].path_mappings must be an array of tables")
    out = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each path_mappings entry must be a table")
        remote_path = str(item.get("remote", "")).rstrip("/")
        local_path = str(item.get("local", "")).rstrip("/")
        if not remote_path or not local_path:
            raise ValueError("each path_mappings entry requires remote and local")
        out.append({"remote": remote_path, "local": local_path})
    out.sort(key=lambda x: len(x["remote"]), reverse=True)
    return out

def translate_remote_to_local(path: str, mappings: list[dict]) -> str | None:
    for item in mappings:
        remote_path = item["remote"]
        if path == remote_path or path.startswith(remote_path + "/"):
            return item["local"] + path[len(remote_path):]
    return None

def validation_commands(cfg: dict) -> list[str]:
    v = cfg.get("validation", {})
    commands = v.get("commands", [])
    if not isinstance(commands, list) or not all(isinstance(x, str) for x in commands):
        raise ValueError("[validation].commands must be an array of strings")
    return commands

def discover(start: str) -> dict:
    repo = git_root(start)
    config_path, cfg = load_config(repo)
    execution = str(cfg.get("execution", "")).strip().lower()
    if execution not in {"local", "remote"}:
        raise ValueError('execution must be "local" or "remote"')

    origin_raw = git_origin(repo)
    origin = normalize_origin(origin_raw)
    repo_name = origin.rsplit("/", 1)[-1] if "/" in origin else repo.name

    result = {
        "project_root": str(repo),
        "config_path": str(config_path),
        "execution": execution,
        "origin_raw": origin_raw,
        "origin": origin,
        "repo_name": repo_name,
        "max_iterations": int(cfg.get("max_iterations", 5)),
        "branch_prefix": str(cfg.get("branch_prefix", "chatgpt-worker/")),
        "validation_commands": validation_commands(cfg),
        "path_mappings": path_mappings(cfg) if execution == "remote" else [],
    }

    if execution == "local":
        result.update({
            "target_host": None,
            "target_repo": str(repo),
            "repo_roots": [],
            "origin_verified": True,
        })
        return result

    remote = cfg.get("remote", {})
    host = str(remote.get("host", "")).strip()
    roots = remote.get("repo_roots", [])
    if not host:
        raise ValueError("[remote].host is required when execution = \"remote\"")
    if not isinstance(roots, list) or not roots or not all(isinstance(x, str) and x.strip() for x in roots):
        raise ValueError("[remote].repo_roots must be a non-empty array of paths")

    candidates = candidate_remote_repos(host, roots, repo_name)
    matches = []
    inspected = []
    for path in candidates:
        r_origin_raw = remote_origin(host, path)
        if not r_origin_raw:
            continue
        r_origin = normalize_origin(r_origin_raw)
        inspected.append({"path": path, "origin": r_origin})
        if r_origin == origin:
            matches.append(path)

    if not matches:
        result.update({
            "target_host": host,
            "target_repo": None,
            "repo_roots": roots,
            "origin_verified": False,
            "inspected_candidates": inspected,
        })
        return result
    if len(matches) > 1:
        raise RuntimeError(
            "Multiple remote repositories match the same origin: " + ", ".join(matches)
        )

    result.update({
        "target_host": host,
        "target_repo": matches[0],
        "target_repo_local_mount": translate_remote_to_local(matches[0], result["path_mappings"]),
        "repo_roots": roots,
        "origin_verified": True,
        "inspected_candidates": inspected,
    })
    return result

def main():
    parser = argparse.ArgumentParser(description="Discover chatgpt-worker project execution target.")
    parser.add_argument("--project", default=os.getcwd(), help="Path inside the opened Git project")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()
    try:
        data = discover(args.project)
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"ok": True, **data}, indent=2))
    else:
        for key, value in data.items():
            if isinstance(value, list):
                print(f"{key}:")
                for item in value:
                    print(f"  - {item}")
            else:
                print(f"{key}: {value}")

if __name__ == "__main__":
    main()
