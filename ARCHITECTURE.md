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
- safe validation and review loop;
- task-branch-only Git communication protocol with immutable request/response files.

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


## Git communication layer

The host adapter should treat Git as the authoritative worker communication bus.

```text
host adapter
   ↓
task branch
   ↓
.chatgpt-worker/sessions/<session>/
   ├── requests/
   └── responses/
   ↓
ChatGPT Web worker
```

The browser/UI transport only wakes the worker and points it at the pending request. Completion is determined by fetching and parsing the response file.

Communication runtime is intentionally excluded from the default branch after merge (`retain_on_merge = false`). The task branch is the durable audit history.

The protocol is shared across all future host adapters, so Codex and Claude should reuse it rather than defining separate message formats.
