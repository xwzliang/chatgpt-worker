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
- use lifecycle.py message --send so the configured [browser].transport (manual/native/cdp) and [browser].auto_allow settings are respected;
- do not bypass the configured transport by calling send_message.js directly;
- in native mode, use CDP only for reload/text insertion and UI.Vision XClick for the final Send action;
- in cdp mode, use the bundled send_message.js direct messenger;
- if [browser].auto_allow=true, let lifecycle.py automatically start/reuse auto_allow before every automated send; do not duplicate daemon startup logic;
- in manual mode, require the user to paste/send the prepared wake-up message;
- never ask the user to relay routine messages to ChatGPT Web or to say "check response";
- poll Git for a committed finished response instead of relying on browser prose;
- keep the opened user workspace untouched by worker task branches/worktrees;
- validate the exact implementation commit using the configured local or remote execution environment.

If the user says phrases such as "don't use chatgpt-worker", "do this directly", or otherwise clearly opts out, respect that request for the current task.

Mandatory lesson workflow:
- BEFORE coding, debugging, or refactoring, consult both .agents/rules/project-lessons.md and the chatgpt-worker managed project-lessons section in AGENTS.md.
- BEFORE concluding any non-trivial task that diagnosed a root cause, fixed broken behavior, discovered a framework quirk, established an architectural invariant, or exposed a tooling/test gotcha, proactively add or refine the verified project lesson.
- Treat this lesson update as part of Definition of Done; do not wait for the user to remind you.
- repository-specific durable conventions/traps -> .agents/rules/project-lessons.md and keep the managed AGENTS.md policy intact;
- truly cross-project reusable engineering techniques/traps -> the global chatgpt-worker-learnings skill.
Do not persist one-off task details, secrets, credentials, temporary paths, transient failures, or unverified guesses.
"""

PROJECT_LESSONS = """# Project Lessons & Mandatory Engineering Rules

> [!IMPORTANT]
> **MANDATORY AGENT WORKFLOW RULE**:
> 1. **Before any coding, debugging, or refactoring**: Consult the lessons and traps in this file to avoid re-introducing documented regressions or fighting known framework pitfalls.
> 2. **Before concluding ANY task**: If the task involved diagnosing an unexpected bug, fixing broken behavior (such as blocked clicks, layout shifts, coordinate offsets, performance lag, or stuck cursors), or learning a non-obvious framework behavior (for example SwiftUI, AppKit, PDFKit, SQLite, browser automation, build systems, or other project frameworks), **YOU MUST PROACTIVELY UPDATE THIS FILE** before declaring completion.
> 3. **Definition of Done**: Updating this file with verified traps and durable rules is part of the definition of done for non-trivial tasks. Do not wait for the user to ask or remind you.

---

## Lesson Maintenance Protocol

### Mandatory Update Triggers

Add or refine a lesson whenever:

- **Root Cause Diagnosed**: A non-obvious failure cause was identified, such as event interception, coordinate shifts, view thrashing, stale state, invalid caching assumptions, or hidden lifecycle behavior.
- **Framework Quirk Discovered**: An unexpected behavior in the project's frameworks or libraries was solved with a specific workaround.
- **Architectural Invariant Established**: A design decision was made that must be maintained across sessions to avoid regressions.
- **Tooling / Test Gotcha Encountered**: A specific build command, test isolation requirement, environment constraint, or setup step was learned.

### Entry Format

Structure each entry concisely with actionable rules:

- **Trap / Problem**: Concise description of symptom and root cause.
- **Rule / Invariant**: Concrete coding rule or pattern to prevent recurrence.

### What NOT to Add

- One-off temporary debugging states or scratch script paths.
- Secrets, credentials, or personal information.
- Unverified hypotheses or narrative conversation history.

## Verified Project Lessons

<!-- Add concise verified lessons below this line. -->
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

AGENTS_BEGIN = "<!-- chatgpt-worker:project-lessons-policy:begin -->"
AGENTS_END = "<!-- chatgpt-worker:project-lessons-policy:end -->"

def agents_policy_section() -> str:
    return (
        AGENTS_BEGIN + "\n"
        + PROJECT_LESSONS.rstrip() + "\n"
        + AGENTS_END + "\n"
    )

def ensure_managed_section(path: pathlib.Path, section: str, begin: str, end: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(section, encoding="utf-8")
        return "created"

    existing = path.read_text(encoding="utf-8")
    start = existing.find(begin)
    finish = existing.find(end)
    if start >= 0 and finish >= start:
        finish += len(end)
        updated = existing[:start] + section.rstrip("\n") + existing[finish:]
        if updated != existing:
            path.write_text(updated, encoding="utf-8")
            return "updated"
        return "unchanged"

    separator = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    path.write_text(existing + separator + section, encoding="utf-8")
    return "appended"

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
    agents_file=root/"AGENTS.md"
    global_skill=pathlib.Path(args.global_skill).expanduser()

    created={
        "workspace_rule": ensure_file(workspace_rule,RULE_TEXT,args.force),
        "project_lessons": ensure_file(lessons,PROJECT_LESSONS,False),
        "agents_md": ensure_managed_section(agents_file, agents_policy_section(), AGENTS_BEGIN, AGENTS_END),
        "global_learning_skill": ensure_file(global_skill,GLOBAL_SKILL,False),
    }
    print(json.dumps({
        "ok":True,
        "project_root":str(root),
        "workspace_rule":str(workspace_rule),
        "project_lessons":str(lessons),
        "agents_md":str(agents_file),
        "global_learning_skill":str(global_skill),
        "created":created,
        "note":"For strongest IDE persistence, set the workspace chatgpt-worker rule activation mode to Always On if the UI exposes activation modes."
    },indent=2))

def cmd_status(args):
    root=git_root(args.project)
    paths={
        "workspace_rule":root/".agents/rules/chatgpt-worker.md",
        "project_lessons":root/".agents/rules/project-lessons.md",
        "agents_md":root/"AGENTS.md",
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
