# Architecture

`chatgpt-worker` separates **shared orchestration primitives** from **host/platform adapters**.

```text
chatgpt-worker/
├── scripts/                  # shared, platform-agnostic helpers
│   ├── discover.py
│   ├── doctor.sh
│   ├── lifecycle.py
│   ├── path_translate.py
│   ├── protocol.py
│   ├── remote.sh
│   ├── send_message.js       # Chrome DevTools Protocol automated messenger
│   ├── auto_allow.swift      # macOS Accessibility API auto-approval daemon source
│   ├── auto_allow.sh         # auto_allow smart launcher
│   └── auto-allow-chrome.sh  # AppleScript fallback auto-allow daemon
├── examples/                 # shared project configuration examples
├── platforms/
│   ├── antigravity/          # implemented host adapter
│   ├── codex/                # placeholder
│   └── claude/               # placeholder
├── skills/
│   ├── chatgpt-worker/       # primary workflow skill
│   └── chatgpt-web-messenger/# browser messaging and auto-allow skill
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


## Lifecycle layer

`scripts/lifecycle.py` owns task-branch and worktree mechanics shared by every future host adapter.

It deliberately separates three Git views:

1. **Opened project** — user-controlled workspace; never switched to the worker task branch.
2. **Control worktree** — local checkout of the audit/task branch containing Git communication runtime.
3. **Validation worktree** — disposable detached checkout of the exact implementation commit; local or remote depending on project configuration.

A fourth branch can be produced for integration:

4. **Delivery branch** — rebuilt from the base branch by cherry-picking only recorded implementation commits. This branch contains no `.chatgpt-worker/` runtime and is suitable for PR/merge.

Host adapters should call this lifecycle rather than reimplementing worktree/branch management.
 
 
## Browser transport layer (CDP & auto_allow)

ChatGPT Web automation relies on two dedicated primitives to eliminate user interruptions:

1. **`scripts/send_message.js`**:
   - Connects to Chrome DevTools Protocol over WebSocket (via `DevToolsActivePort`).
   - Targets the open ChatGPT tab (`chatgpt.com/c/...` or `chatgpt.com`).
   - **Always executes `location.reload()` before typing** to clear stale WebSockets and ProseMirror DOM states.
   - Waits for `#prompt-textarea` to mount, injects text via CDP `Input.insertText`, clicks send, and verifies DOM delivery.

2. **`scripts/auto_allow` / `auto_allow.sh`**:
   - Native daemon running in the background on macOS using the Accessibility API (`AXUIElement`).
   - Automatically detects and presses "Allow" on Chrome's "Allow remote debugging?" consent prompt within 500ms.
   - Prevents popup interruptions when external CDP connections attach to port 9222.

