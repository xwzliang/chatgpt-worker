#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

RULE_TEXT = """# chatgpt-worker workspace rule

For substantive coding, debugging, implementation, refactoring, testing, or code-review requests in this workspace, use the installed chatgpt-worker workflow by default unless the user explicitly asks not to use it or asks for a simple direct answer that does not require repository changes.

Do not require the user to type /chatgpt-worker again after this rule has been installed.

Before starting worker execution:
- use the opened workspace/repository as project scope;
- ensure .chatgpt-worker.toml exists, running guided first-run configuration if needed;
- use the Git-backed task-branch communication protocol;
- use the bundled chatgpt-web-messenger / send_message.js to automate ChatGPT Web messaging with automatic page refresh before sending;
- ensure the background auto_allow daemon is running to auto-approve Chrome remote debugging consent prompts;
- never ask the user to relay routine messages to ChatGPT Web or to say "check response";
- poll Git for a committed finished response instead of relying on browser prose;
- keep the opened user workspace untouched by worker task branches/worktrees;
- validate the exact implementation commit using the configured local or remote execution environment.

If the user says phrases such as "don't use chatgpt-worker", "do this directly", or otherwise clearly opts out, respect that request for the current task.

After meaningful development/debugging work, review whether any durable lesson should be persisted:
- repository-specific durable conventions/traps -> .agents/rules/project-lessons.md;
- truly cross-project reusable engineering techniques/traps -> the global chatgpt-worker-learnings skill.
Do not persist one-off task details, secrets, credentials, temporary paths, transient failures, or unverified guesses.
"""

PROJECT_LESSONS = """# Project lessons

Maintain concise, durable lessons that are useful for future work in THIS repository.

Only add a lesson when it is verified and likely to recur. Prefer actionable rules over narrative history.

Good examples:
- required test commands or setup steps that are easy to miss;
- architectural invariants;
- recurring framework/build-system traps;
- repository-specific conventions that prevent regressions.

Do not add:
- one-off task details;
- temporary debugging state;
- secrets or credentials;
- personal information;
- speculative/unverified conclusions.
"""

GLOBAL_SKILL = """---
name: chatgpt-worker-learnings
description: Reusable cross-project engineering lessons, traps, debugging techniques, and development practices learned during chatgpt-worker tasks. Consult when a coding/debugging task may benefit from previously learned general techniques.
---

# ChatGPT Worker Learnings

This file is a curated cross-project knowledge base.

## Promotion criteria

Add a lesson only when it is:
1. verified by code/tests/docs/observed behavior;
2. useful beyond the current repository or likely useful in multiple future projects;
3. concise and actionable;
4. free of secrets, credentials, personal data, repository-specific identifiers, and temporary machine paths.

Prefer lessons with this shape:

### <short title>
- **When:** recognizable situation/symptom.
- **Lesson:** reusable rule or technique.
- **Why:** concise reason/evidence.
- **Action:** what to do next time.

Do not copy raw logs or project history here. Repository-specific lessons belong in the repository's .agents/rules/project-lessons.md instead.

## Learned lessons

<!-- Curated lessons are appended below this line. -->
"""

def git_root(start: str) -> pathlib.Path:
    p=subprocess.run(["git","rev-parse","--show-toplevel"],cwd=start,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "not inside a Git repository")
    return pathlib.Path(p.stdout.strip()).resolve()

def ensure_file(path: pathlib.Path, content: str, overwrite: bool=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and not overwrite:
        return False
    path.write_text(content,encoding="utf-8")
    return True

def cmd_enable(args):
    root=git_root(args.project)
    workspace_rule=root/".agents/rules/chatgpt-worker.md"
    lessons=root/".agents/rules/project-lessons.md"
    global_skill=pathlib.Path(args.global_skill).expanduser()

    created={
        "workspace_rule": ensure_file(workspace_rule,RULE_TEXT,args.force),
        "project_lessons": ensure_file(lessons,PROJECT_LESSONS,False),
        "global_learning_skill": ensure_file(global_skill,GLOBAL_SKILL,False),
    }
    print(json.dumps({
        "ok":True,
        "project_root":str(root),
        "workspace_rule":str(workspace_rule),
        "project_lessons":str(lessons),
        "global_learning_skill":str(global_skill),
        "created":created,
        "note":"For strongest IDE persistence, set the workspace chatgpt-worker rule activation mode to Always On if the UI exposes activation modes."
    },indent=2))

def cmd_status(args):
    root=git_root(args.project)
    paths={
        "workspace_rule":root/".agents/rules/chatgpt-worker.md",
        "project_lessons":root/".agents/rules/project-lessons.md",
        "global_learning_skill":pathlib.Path(args.global_skill).expanduser(),
    }
    print(json.dumps({
        "ok":True,
        "project_root":str(root),
        "paths":{k:str(v) for k,v in paths.items()},
        "exists":{k:v.exists() for k,v in paths.items()},
    },indent=2))

def main():
    p=argparse.ArgumentParser(description="Bootstrap persistent chatgpt-worker workspace behavior and learning files")
    sub=p.add_subparsers(dest="cmd",required=True)
    for name in ("enable","status"):
        s=sub.add_parser(name)
        s.add_argument("--project",default=".")
        s.add_argument("--global-skill",default="~/.gemini/config/skills/chatgpt-worker-learnings/SKILL.md")
        if name=="enable":
            s.add_argument("--force",action="store_true")
        s.set_defaults(func=cmd_enable if name=="enable" else cmd_status)
    args=p.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(json.dumps({"ok":False,"error":str(exc)},indent=2),file=sys.stderr)
        sys.exit(1)

if __name__=="__main__":
    main()
