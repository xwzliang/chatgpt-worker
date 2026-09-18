# chatgpt-worker

A host-extensible coding-worker framework that uses **ChatGPT Web as a coding worker** and a local host agent as the orchestrator/reviewer. **Antigravity is the currently implemented host adapter**; Codex and Claude are reserved for future adapters but are not implemented yet.

The intended loop is:

```text
Antigravity on macOS
  ├─ native browser → ChatGPT Web → connected GitHub repository
  └─ SSH → Linux validation environment
                  ↓
        fetch / diff / test / build
                  ↓
             feedback to ChatGPT
                  ↓
                repeat
```

ChatGPT Web makes code changes through its GitHub connection. Antigravity independently pulls the task branch on Linux, runs validation, reviews the diff, and sends failures back to the same ChatGPT conversation.

## Install

### Antigravity IDE on macOS

One-line install/update:

```bash
curl -fsSL https://raw.githubusercontent.com/xwzliang/chatgpt-worker/master/install.sh | bash
```

Or clone it first:

```bash
git clone https://github.com/xwzliang/chatgpt-worker.git
cd chatgpt-worker
bash install.sh
```

The installer places the plugin at:

```text
~/.gemini/config/plugins/chatgpt-worker
```

Running the installer again updates an existing Git-backed installation. On macOS, the installer then gracefully quits and relaunches Antigravity IDE so the newly installed plugin is discovered immediately. Use `--no-relaunch` if you do not want this behavior.

### Antigravity CLI

```bash
git clone https://github.com/xwzliang/chatgpt-worker.git
cd chatgpt-worker
bash install.sh --cli
```

This delegates installation to `agy plugin install`.

## Linux server setup

Configure an SSH alias on the Mac, for example:

```sshconfig
Host ai-server
    HostName 192.168.1.123
    User your-linux-user
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

Then verify:

```bash
ssh ai-server 'uname -a'
```

The bundled helper uses `ai-server` by default. Override it with:

```bash
export CHATGPT_WORKER_HOST=my-server
```

Examples:

```bash
bash scripts/remote.sh exec uname -a
bash scripts/remote.sh repo /srv/my-project git status --short
bash scripts/remote.sh test /srv/my-project 'pytest -q'
```

## Recommended workflow

Use a dedicated task branch such as `chatgpt-worker/fix-auth` and a disposable Linux validation worktree. ChatGPT edits the remote task branch; Antigravity fetches and validates it. Avoid having both agents edit the same working tree.

Once Antigravity discovers the plugin, invoke:

```text
/chatgpt-worker
```

The skill directs Antigravity to open/reuse a ChatGPT Web conversation, delegate coding through ChatGPT's connected GitHub repository, validate remotely over SSH, review the diff, feed failures back, and iterate until validation passes or the repair limit is reached.

## Safety

ChatGPT Web is treated as a coding worker, not as the final authority. The plugin does not authorize automatic merging by default and instructs Antigravity not to expose secrets or perform destructive/privileged Linux operations without explicit user authorization.


## Per-project configuration

The opened Antigravity project folder is the source of project identity. Add a repository-root file named `.chatgpt-worker.toml` to choose where validation runs.

### Local project

```toml
execution = "local"

branch_prefix = "chatgpt-worker/"
max_iterations = 5

[validation]
commands = [
  "npm run typecheck",
  "npm test",
  "npm run build",
]
```

In local mode, ChatGPT still edits the connected GitHub repository, while Antigravity validates the fetched task branch on the Mac. The skill prefers a disposable worktree so the opened working tree is not disturbed.

### Remote project

```toml
execution = "remote"

branch_prefix = "chatgpt-worker/"
max_iterations = 5

[remote]
host = "ai-server"
repo_roots = [
  "/mnt/omv/git",
  "/home/broliang/git",
]

[[remote.path_mappings]]
remote = "/mnt/omv"
local = "/Volumes/omv"

[validation]
commands = [
  "pytest -q",
  "ruff check .",
]
```

The SSH alias itself should be configured in `~/.ssh/config`. In remote mode, the plugin:

1. Reads the opened local repository's Git `origin`.
2. Normalizes it to a repository identity such as `xwzliang/project`.
3. Connects to the configured SSH host.
4. Searches only the configured `repo_roots`.
5. Selects a remote repository only when its normalized Git `origin` matches the local repository.

Directory names are only used as a fast candidate guess; Git-origin equality is the actual identity check.

Examples are included at:

```text
examples/project-config-local.toml
examples/project-config-remote.toml
```

## Discovery check

After adding `.chatgpt-worker.toml`, verify the project before starting a coding loop:

```bash
~/.gemini/config/plugins/chatgpt-worker/scripts/doctor.sh
```

For machine-readable discovery:

```bash
~/.gemini/config/plugins/chatgpt-worker/scripts/discover.py --json
```

A ready remote project reports the opened repo, normalized Git origin, SSH host, matched remote repo, validation commands, and `Status: READY`.


## Remote-to-local mounted paths

A remote project can declare that a Linux path and a macOS path refer to the same mounted storage:

```toml
[[remote.path_mappings]]
remote = "/mnt/omv"
local = "/Volumes/omv"
```

With this mapping, a Linux-generated artifact such as:

```text
/mnt/omv/resources/output/result.mp4
```

can be inspected directly on the Mac at:

```text
/Volumes/omv/resources/output/result.mp4
```

The plugin should prefer that direct local inspection when the mapped mount exists instead of copying the artifact back over SSH.

You can translate a path manually with:

```bash
~/.gemini/config/plugins/chatgpt-worker/scripts/path_translate.py \
  /mnt/omv/resources/output/result.mp4 \
  --config .chatgpt-worker.toml
```

## Extensible host architecture

Shared logic lives in `scripts/` and project configuration remains platform-independent.

Host-specific adapters live under:

```text
platforms/
├── antigravity/   # implemented
├── codex/         # placeholder only
└── claude/        # placeholder only
```

See `ARCHITECTURE.md` for the extension contract. Future adapters should reuse the same `.chatgpt-worker.toml`, Git-origin discovery, path mappings, validation rules, and worker-loop semantics rather than creating parallel implementations.


## Git-backed communication on task branches

The orchestrator and ChatGPT Web now communicate primarily through Git, not by parsing browser replies.

Runtime communication lives only on a dedicated task branch:

```text
.chatgpt-worker/
├── PROTOCOL.md
└── sessions/
    └── <session-id>/
        ├── session.json
        ├── requests/
        │   ├── 0001.md
        │   └── ...
        └── responses/
            ├── 0001.json
            └── ...
```

The default branch should stay clean. With:

```toml
[communication]
runtime_dir = ".chatgpt-worker"
retain_on_merge = false
```

the task branch keeps the full audit trail, while communication files are omitted/removed from the merge result.

Browser messages are intentionally minimal: repository, branch, session, and request ID. The actual task or validation feedback lives in the request file.

A completed request uses two commits:

1. an implementation commit containing the code change;
2. a response commit containing `responses/NNNN.json`, which records the `implementation_commit` SHA.

The host fetches the task branch, reads the response JSON, validates the implementation commit, and then runs tests/review.

The canonical protocol is in `protocol/PROTOCOL.md`; `scripts/protocol.py` provides helpers for session creation, request creation, response checks, and session state updates.


## Automatic task-branch/worktree lifecycle

The plugin now provides `scripts/lifecycle.py`, which keeps the Antigravity-opened repository untouched while managing task branches and disposable worktrees automatically.

The normal flow is:

```text
opened project
    │
    ├─ remains on user's current branch
    │
    └─ lifecycle creates:
         ├─ control worktree → audit/task branch
         └─ validation worktree → exact implementation commit
```

For remote projects, the validation worktree is created on the configured Linux host beside the discovered remote repository.

Core commands:

```bash
# 1. Create task branch, control worktree, session, request 0001, commit and push
scripts/lifecycle.py start \
  --project . \
  --task "Fix authentication handling" \
  --request-file /tmp/request.md

# 2. Query current lifecycle state
scripts/lifecycle.py status --state-file <state-file>

# 3. Fetch the audit branch and check whether ChatGPT wrote its response
scripts/lifecycle.py response --state-file <state-file>

# 4. Create/update validation worktree at the exact implementation commit
scripts/lifecycle.py prepare-validation --state-file <state-file>

# 5. Run configured validation commands
scripts/lifecycle.py validate --state-file <state-file>

# 6. Append the next feedback request if needed
scripts/lifecycle.py next-request \
  --state-file <state-file> \
  --type validation_failure \
  --request-file /tmp/feedback.md

# 7. Build a clean branch containing only implementation commits
scripts/lifecycle.py prepare-delivery --state-file <state-file>

# 8. Persist final session state and clean disposable worktrees
scripts/lifecycle.py finish --state-file <state-file> --status completed
```

Lifecycle state is stored outside the repository under:

```text
~/.cache/chatgpt-worker/tasks/
```

The task/audit branch is preserved after cleanup.

### Audit branch vs delivery branch

The audit branch contains both code and the complete Git communication history:

```text
chatgpt-worker/fix-auth
├── source changes
└── .chatgpt-worker/
    └── requests / responses / session state
```

The delivery branch is reconstructed from the original base branch by cherry-picking only implementation commits:

```text
chatgpt-worker/fix-auth-delivery
└── source changes only
```

Use the delivery branch for a PR or merge. This enforces the task-branch-only communication model while retaining the audit branch for history.


## First-run project setup

If an opened project has no `.chatgpt-worker.toml`, Antigravity should guide configuration instead of stopping.

It first inspects the project and SSH configuration:

```bash
~/.gemini/config/plugins/chatgpt-worker/scripts/configure.py inspect --project .
```

This reports the Git project root, whether a config already exists, and concrete host aliases parsed from `~/.ssh/config`.

Antigravity then asks whether the project should execute locally or remotely.

For **local** execution, it writes the config directly after confirming/inferring validation commands:

```bash
scripts/configure.py write \
  --project . \
  --execution local \
  --validation-command "npm test"
```

For **remote** execution, Antigravity presents the detected SSH aliases, asks which one to use, asks for one or more remote repo roots, and optionally records path mappings such as:

```text
/mnt/omv=/Volumes/omv
```

Example:

```bash
scripts/configure.py write \
  --project . \
  --execution remote \
  --host ai-server \
  --repo-root /mnt/omv/git \
  --path-mapping /mnt/omv=/Volumes/omv \
  --validation-command "pytest -q"
```

It then reruns `doctor.sh`. Once the project reports `Status: READY`, the normal task lifecycle can begin.

Existing config files are not overwritten unless `--force` is explicitly used.


## One-time activation per project

You do **not** need to type `/chatgpt-worker` before every message.

On the first explicit use in a repository, bootstrap persistent workspace behavior:

```bash
~/.gemini/config/plugins/chatgpt-worker/scripts/workspace_bootstrap.py enable --project .
```

This creates:

```text
.agents/
└── rules/
    ├── chatgpt-worker.md
    └── project-lessons.md

~/.gemini/config/skills/
└── chatgpt-worker-learnings/
    └── SKILL.md
```

The workspace rule tells Antigravity to use chatgpt-worker automatically for substantive coding/debugging/repository-changing work unless you explicitly opt out for a task.

In Antigravity IDE, if the workspace-rule UI exposes activation modes, set `chatgpt-worker.md` to **Always On** for the strongest persistence.

### Learning scopes

Use three distinct scopes:

1. **Workspace auto-use rule**
   - `.agents/rules/chatgpt-worker.md`
   - controls whether chatgpt-worker should be used automatically in this repository.

2. **Repository-specific durable lessons**
   - `.agents/rules/project-lessons.md`
   - architecture invariants, setup requirements, recurring repository-specific traps and conventions.

3. **Cross-project reusable lessons**
   - `~/.gemini/config/skills/chatgpt-worker-learnings/SKILL.md`
   - verified, portable engineering techniques and traps useful in other projects.

The agent should actively review these after meaningful development/debugging work, but only persist durable, verified information. One-off task details, secrets, temporary logs, machine-specific paths, and unverified guesses should not be promoted.


## Fully automated ChatGPT Web handoff

Antigravity should not ask you to copy a wake-up message into ChatGPT Web or later reply with `check response`. Everything is self-contained and automated via the Chrome DevTools Protocol (CDP).

For each worker request the automated flow is:

```text
create/push request commit
        ↓
auto_allow daemon approves Chrome debugging prompt (if prompted)
        ↓
send_message.js connects to Chrome via CDP
        ↓
send_message.js refreshes page first (clears stale sockets/DOM)
        ↓
send_message.js waits for #prompt-textarea and injects wake-up message
        ↓
ChatGPT Web reads request from GitHub
        ↓
implementation commit
        ↓
response commit with finished=true
        ↓
Antigravity polls Git automatically (wait-response)
        ↓
validate exact implementation commit
```

### 1. Browser Messenger & Pre-Send Page Reload
ChatGPT Web's ProseMirror editor frequently enters a stale or unresponsive state if left open in the background. The bundled messenger script (`scripts/send_message.js`) solves this by:
1. Discovering the Chrome DevTools active port automatically.
2. Attaching to the ChatGPT conversation tab (`chatgpt.com/c/...` or `chatgpt.com`).
3. **Always refreshing the page (`location.reload()`)** before typing.
4. Waiting for `#prompt-textarea` to mount and become interactive.
5. Ingesting the message via CDP `Input.insertText` and clicking send.
6. Verifying delivery in the DOM before returning.

To send a message via lifecycle helper:
```bash
python3 scripts/lifecycle.py message --state-file <state-file> --send
```

Or run the script directly:
```bash
node scripts/send_message.js --file /path/to/message.txt
# OR
node scripts/send_message.js "Your message here"
```

### 2. Auto-Approving Chrome's Remote Debugging Prompts
Modern Google Chrome (136+) shows a modal sheet:
`"Allow remote debugging? An external app wants full control over this Chrome session to debug it..."`

A background daemon handles this automatically using the macOS Accessibility API:

```bash
# Start auto-allow daemon
bash scripts/auto_allow.sh start

# Check status
bash scripts/auto_allow.sh status

# Stop daemon
bash scripts/auto_allow.sh stop
```

The daemon automatically compiles native `scripts/auto_allow` with `swiftc` on first run (or falls back to AppleScript if `swiftc` is unavailable). It detects and clicks "Allow" within 500ms so you are never interrupted.

### 3. Chrome Setup
To enable Chrome DevTools remote debugging:
- **Option A**: Open `chrome://inspect/#remote-debugging` in Chrome and verify the checkbox is enabled.
- **Option B**: Start Chrome with remote debugging enabled:
  ```bash
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 &
  ```

Run `scripts/doctor.sh` at any time to verify that your Git origin, Node.js, Chrome DevTools, and auto_allow are all in a ready state:
```bash
bash scripts/doctor.sh
```

---

### 4. Git Polling & Verification

The Git watcher is:

```bash
scripts/lifecycle.py wait-response \
  --state-file <state-file>
```

Defaults:
- poll interval: 10 seconds
- timeout: 1800 seconds

These can be overridden with `--interval` and `--timeout`.

A request is considered finished only when all of the following are true:
1. the remote task branch has advanced beyond the request commit;
2. the matching committed response JSON exists;
3. `status` is `completed`;
4. `finished` is `true`;
5. `finish_message` is non-empty;
6. `implementation_commit` exists and is reachable from the task branch.

Example response:

```json
{
  "protocol_version": 1,
  "request_id": "0001",
  "status": "completed",
  "finished": true,
  "implementation_commit": "abc123def456",
  "finish_message": "Implementation is complete and pushed.",
  "summary": "Fixed the dashboard refresh bug.",
  "files_changed": [
    "src/pages/DashboardPage.tsx"
  ],
  "notes": []
}
```

Browser prose such as "done" is never the authoritative completion signal.

If the watcher times out, Antigravity inspects the same ChatGPT Web conversation itself. User involvement is only needed for a genuine blocker such as authentication or an ambiguous decision—not for routine message relay or polling.

