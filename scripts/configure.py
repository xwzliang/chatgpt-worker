#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shlex
import subprocess
import sys
from typing import Any

CONFIG_NAME = ".chatgpt-worker.toml"

def git_root(start: str) -> pathlib.Path:
    p=subprocess.run(["git","rev-parse","--show-toplevel"],cwd=start,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "not inside a Git repository")
    return pathlib.Path(p.stdout.strip()).resolve()

def ssh_aliases(path: pathlib.Path) -> list[str]:
    if not path.is_file():
        return []
    aliases=[]
    for raw in path.read_text(encoding="utf-8",errors="ignore").splitlines():
        line=raw.strip()
        if not line or line.startswith("#"):
            continue
        m=re.match(r"(?i)^host\s+(.+)$",line)
        if not m:
            continue
        for token in shlex.split(m.group(1)):
            # Ignore wildcard/pattern entries; they are not concrete selectable hosts.
            if any(ch in token for ch in "*?!"):
                continue
            if token not in aliases:
                aliases.append(token)
    return aliases

def toml_quote(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)

def render_local(args) -> str:
    lines=[
        'execution = "local"',
        '',
        f'branch_prefix = {toml_quote(args.branch_prefix)}',
        f'max_iterations = {args.max_iterations}',
        '',
        '[browser]',
        f'transport = {toml_quote(args.browser_transport)}',
        f'auto_allow = {str(args.auto_allow).lower()}',
    ]
    if args.uivision_autorun_html:
        lines.append(f'uivision_autorun_html = {toml_quote(args.uivision_autorun_html)}')
    if args.browser_transport == "native":
        lines.append(f'uivision_macro_name = {toml_quote(args.uivision_macro_name)}')
    lines += [
        '',
        '[validation]',
        'commands = [',
    ]
    for cmd in args.validation_command:
        lines.append(f'  {toml_quote(cmd)},')
    lines += [
        ']',
        '',
        '[communication]',
        'runtime_dir = ".chatgpt-worker"',
        'retain_on_merge = false',
        '',
    ]
    return "\n".join(lines)

def render_remote(args) -> str:
    if not args.host:
        raise ValueError("--host is required for remote configuration")
    if not args.repo_root:
        raise ValueError("at least one --repo-root is required for remote configuration")
    lines=[
        'execution = "remote"',
        '',
        f'branch_prefix = {toml_quote(args.branch_prefix)}',
        f'max_iterations = {args.max_iterations}',
        '',
        '[browser]',
        f'transport = {toml_quote(args.browser_transport)}',
    ]
    if args.uivision_autorun_html:
        lines.append(f'uivision_autorun_html = {toml_quote(args.uivision_autorun_html)}')
    if args.browser_transport == "native":
        lines.append(f'uivision_macro_name = {toml_quote(args.uivision_macro_name)}')
    lines += [
        '',
        '[remote]',
        f'host = {toml_quote(args.host)}',
        'repo_roots = [',
    ]
    for root in args.repo_root:
        lines.append(f'  {toml_quote(root)},')
    lines += [']','']
    for mapping in args.path_mapping:
        if "=" not in mapping:
            raise ValueError("--path-mapping must be REMOTE=LOCAL")
        remote, local = mapping.split("=",1)
        if not remote or not local:
            raise ValueError("--path-mapping must be REMOTE=LOCAL")
        lines += [
            '[[remote.path_mappings]]',
            f'remote = {toml_quote(remote)}',
            f'local = {toml_quote(local)}',
            '',
        ]
    lines += ['[validation]','commands = [']
    for cmd in args.validation_command:
        lines.append(f'  {toml_quote(cmd)},')
    lines += [
        ']',
        '',
        '[communication]',
        'runtime_dir = ".chatgpt-worker"',
        'retain_on_merge = false',
        '',
    ]
    return "\n".join(lines)

def cmd_inspect(args):
    root=git_root(args.project)
    config=root/CONFIG_NAME
    ssh_path=pathlib.Path(args.ssh_config).expanduser()
    uivision_candidates=[
        pathlib.Path("~/uivision/ui.vision.html").expanduser(),
        pathlib.Path("~/Desktop/uivision/ui.vision.html").expanduser(),
    ]
    data={
        "ok":True,
        "project_root":str(root),
        "config_path":str(config),
        "config_exists":config.exists(),
        "ssh_config":str(ssh_path),
        "ssh_aliases":ssh_aliases(ssh_path),
        "uivision_autorun_html_candidates":[str(p) for p in uivision_candidates if p.is_file()],
        "uivision_macro_candidates":[
            str(p) for p in [
                pathlib.Path("~/uivision/macros/ChatGPTClickSendExistingTab.json").expanduser(),
                pathlib.Path("~/Desktop/uivision/macros/ChatGPTClickSendExistingTab.json").expanduser(),
            ] if p.is_file()
        ],
    }
    print(json.dumps(data,indent=2))

def cmd_write(args):
    root=git_root(args.project)
    config=root/CONFIG_NAME
    if config.exists() and not args.force:
        raise RuntimeError(f"{config} already exists; use --force to overwrite")
    if args.execution == "local":
        content=render_local(args)
    else:
        content=render_remote(args)
    config.write_text(content,encoding="utf-8")
    print(json.dumps({"ok":True,"config_path":str(config),"execution":args.execution,"browser_transport":args.browser_transport,"auto_allow":args.auto_allow},indent=2))

def main():
    p=argparse.ArgumentParser(description="First-run configuration helper for chatgpt-worker")
    sub=p.add_subparsers(dest="cmd",required=True)

    i=sub.add_parser("inspect")
    i.add_argument("--project",default=".")
    i.add_argument("--ssh-config",default="~/.ssh/config")
    i.set_defaults(func=cmd_inspect)

    w=sub.add_parser("write")
    w.add_argument("--project",default=".")
    w.add_argument("--execution",required=True,choices=["local","remote"])
    w.add_argument("--host")
    w.add_argument("--repo-root",action="append",default=[])
    w.add_argument("--path-mapping",action="append",default=[])
    w.add_argument("--validation-command",action="append",default=[])
    w.add_argument("--branch-prefix",default="chatgpt-worker/")
    w.add_argument("--max-iterations",type=int,default=5)
    w.add_argument("--browser-transport",choices=["manual","native","cdp"],default="cdp")
    w.add_argument("--auto-allow",action=argparse.BooleanOptionalAction,default=False)
    w.add_argument("--uivision-autorun-html")
    w.add_argument("--uivision-macro-name",default="ChatGPTClickSendExistingTab")
    w.add_argument("--force",action="store_true")
    w.set_defaults(func=cmd_write)

    args=p.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(json.dumps({"ok":False,"error":str(exc)},indent=2),file=sys.stderr)
        sys.exit(1)

if __name__=="__main__":
    main()
