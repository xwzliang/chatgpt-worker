# Antigravity adapter

This is the currently implemented host adapter.

Antigravity-specific responsibilities:

- use the opened Antigravity project folder as project scope;
- invoke the shared discovery helpers;
- use Antigravity's native browser to drive ChatGPT Web;
- use local shell or SSH for validation;
- feed validation/review failures back to the same ChatGPT Web conversation.

The installable Antigravity skill currently remains at `skills/chatgpt-worker/SKILL.md` because that is the format Antigravity discovers. Shared logic should stay in `scripts/`; Antigravity-only instructions should stay in the skill or this adapter directory.
