# Architecture

`chatgpt-worker` separates **shared orchestration primitives** from **host/platform adapters**.

```text
chatgpt-worker/
├── scripts/                  # shared, platform-agnostic helpers
│   ├── discover.py
│   ├── doctor.sh
│   ├── path_translate.py
│   └── remote.sh
├── examples/                 # shared project configuration examples
├── platforms/
│   ├── antigravity/          # implemented host adapter
│   ├── codex/                # placeholder
│   └── claude/               # placeholder
├── skills/chatgpt-worker/    # current Antigravity-discoverable skill entrypoint
└── rules/                    # shared safety rules
```

## Shared contract

Every future host adapter should consume the same repository-root `.chatgpt-worker.toml` and the same discovery result rather than inventing a separate configuration model.

Shared concepts include:

- opened/current Git repository identity;
- normalized Git origin;
- local vs remote execution;
- remote repo discovery by matching Git origin;
- validation commands;
- task branch prefix and iteration limit;
- remote-to-local path mappings;
- safe validation and review loop.

## Host adapter responsibilities

A host adapter decides how its tool:

- discovers the currently opened/scoped project;
- talks to ChatGPT Web;
- invokes shared shell/SSH helpers;
- presents progress and feedback;
- installs/reloads itself in the host.

Host adapters should not duplicate Git-origin discovery, path translation, or project configuration parsing.

## Current status

Antigravity is implemented now. Codex and Claude are intentionally placeholders only. Their presence in `platforms/` does not imply support yet.
