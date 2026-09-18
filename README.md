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
