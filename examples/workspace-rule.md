# chatgpt-worker workspace rule

For substantive coding/debugging/repository-change requests in this workspace, use chatgpt-worker automatically unless the user explicitly opts out.

Do not require /chatgpt-worker on every message. Respect the configured browser transport and auto_allow settings through lifecycle.py rather than bypassing them.

## Mandatory project lesson workflow

Before any coding, debugging, or refactoring:

- consult `.agents/rules/project-lessons.md`;
- consult the chatgpt-worker managed project-lessons policy in `AGENTS.md`.

Before concluding any non-trivial task that diagnosed a root cause, fixed broken behavior, discovered a framework quirk, established an architectural invariant, or exposed a tooling/test gotcha:

- proactively add or refine a verified repository lesson;
- treat this lesson update as part of Definition of Done;
- do not wait for the user to remind you.

Project lessons should use concise **Trap / Problem** and **Rule / Invariant** entries.

Do not persist one-off debugging state, temporary paths, secrets, credentials, personal information, unverified hypotheses, or narrative history.

Cross-project reusable lessons belong in:

`~/.gemini/config/skills/chatgpt-worker-learnings/SKILL.md`
