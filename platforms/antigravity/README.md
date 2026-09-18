# Antigravity adapter

This is the currently implemented host adapter.

Antigravity-specific responsibilities:

- use the opened Antigravity project folder as project scope;
- invoke the shared discovery helpers;
- use Antigravity's native browser to drive ChatGPT Web;
- use local shell or SSH for validation;
- feed validation/review failures back to the same ChatGPT Web conversation.

The installable Antigravity skill currently remains at `skills/chatgpt-worker/SKILL.md` because that is the format Antigravity discovers. Shared logic should stay in `scripts/`; Antigravity-only instructions should stay in the skill or this adapter directory.


## Browser control requirement

ChatGPT Web interaction uses direct Chrome DevTools Protocol (CDP) automation via `scripts/send_message.js` (or `lifecycle.py message --send`).

Key requirements:
1. **Always Refresh Page Before Sending**: ChatGPT Web frequently enters a stale or frozen DOM/WebSocket state if idle. The script automatically executes `location.reload()` before typing.
2. **Auto-Approve Remote Debugging Prompts**: Chrome 136+ displays a modal prompt asking "Allow remote debugging?". The background `auto_allow` daemon (`scripts/auto_allow.sh start`) automatically detects and clicks "Allow" using macOS Accessibility API within ~500ms, eliminating interruptions.
3. **No Subagent Research Loops**: Subagents must not spend time doing exploratory DOM research or reverse-engineering; they must execute the bundled script directly.

Recommended invocation:

```bash
# Start auto-allow daemon in background (macOS only)
bash scripts/auto_allow.sh start

# Send wake-up message and verify delivery
python3 scripts/lifecycle.py message --state-file <state-file> --send
```

The main agent then uses Git polling via `lifecycle.py wait-response`; browser prose is not the completion signal.

