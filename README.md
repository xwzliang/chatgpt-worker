# chatgpt-worker

An Antigravity plugin that uses **Antigravity as the orchestrator/reviewer** and **ChatGPT Web as a coding worker**.

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

```bash
git clone https://github.com/xwzliang/chatgpt-worker.git
cd chatgpt-worker
./install.sh
```

The installer places the plugin at:

```text
~/.gemini/config/plugins/chatgpt-worker
```

Rerun `./install.sh` to update an existing Git-backed installation.

### Antigravity CLI

```bash
./install.sh --cli
```

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
scripts/remote.sh exec uname -a
scripts/remote.sh repo /srv/my-project git status --short
scripts/remote.sh test /srv/my-project 'pytest -q'
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
