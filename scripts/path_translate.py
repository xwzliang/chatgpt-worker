#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import sys

try:
    import tomllib
except ModuleNotFoundError:
    print("Python 3.11+ is required.", file=sys.stderr)
    sys.exit(2)

CONFIG_NAME = ".chatgpt-worker.toml"

def load(path: pathlib.Path):
    with path.open("rb") as f:
        return tomllib.load(f)

def mappings(cfg: dict):
    remote = cfg.get("remote", {})
    items = remote.get("path_mappings", [])
    if not isinstance(items, list):
        raise ValueError("[remote].path_mappings must be an array of tables")
    out=[]
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each path_mappings entry must be a table")
        rp=str(item.get("remote","")).rstrip("/")
        lp=str(item.get("local","")).rstrip("/")
        if not rp or not lp:
            raise ValueError("each path_mappings entry requires remote and local")
        out.append((rp,lp))
    return sorted(out, key=lambda x: len(x[0]), reverse=True)

def translate(path: str, pairs):
    for remote, local in pairs:
        if path == remote or path.startswith(remote + "/"):
            return local + path[len(remote):]
    return None

def main():
    p=argparse.ArgumentParser(description="Translate a remote path to its locally mounted path.")
    p.add_argument("path")
    p.add_argument("--config", default=CONFIG_NAME)
    p.add_argument("--json", action="store_true")
    args=p.parse_args()
    try:
        cfg=load(pathlib.Path(args.config))
        result=translate(args.path, mappings(cfg))
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok":False,"error":str(exc)}))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps({"ok":True,"remote_path":args.path,"local_path":result}, indent=2))
    elif result:
        print(result)
    else:
        sys.exit(3)

if __name__ == "__main__":
    main()
