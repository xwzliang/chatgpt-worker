# Platform adapters

`chatgpt-worker` is intended to support multiple host/orchestrator tools.

Shared project discovery, Git identity checks, SSH execution, path mapping, and validation conventions live outside this directory.

Each supported host gets an adapter under `platforms/<platform>/`.

Current status:

- `antigravity/` — implemented.
- `codex/` — placeholder only; not implemented.
- `claude/` — placeholder only; not implemented.

Do not assume another platform is supported merely because its placeholder directory exists.
