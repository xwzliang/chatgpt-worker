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

ChatGPT Web interaction MUST use Antigravity's native `/browser` slash command.

Do not use any of the following as a substitute:

- `osascript` / AppleScript;
- shell-driven GUI automation;
- simulated keyboard/mouse input;
- Accessibility scripting;
- launching Chrome and trying to type through OS automation.

If `/browser` is unavailable or fails, report the blocker. Do not silently fall back to OS-level UI automation.

Recommended invocation pattern:

```text
/browser Open or focus the existing ChatGPT Web conversation for this chatgpt-worker task.
Send exactly the following wake-up message without changing it:
<message>
After sending it, return control to the main agent.
```

The main agent should then use Git polling via `lifecycle.py wait-response`; browser prose is not the completion signal.
