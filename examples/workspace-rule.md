# chatgpt-worker workspace rule

For substantive coding/debugging/repository-change requests in this workspace, use chatgpt-worker automatically unless the user explicitly opts out.

Do not require /chatgpt-worker on every message.
Use the bundled chatgpt-web-messenger (scripts/send_message.js) to automate ChatGPT Web interactions with pre-send page reload, and ensure auto_allow daemon is running.

Persist verified durable lessons:

- repo-specific lessons -> .agents/rules/project-lessons.md
- cross-project reusable lessons -> ~/.gemini/config/skills/chatgpt-worker-learnings/SKILL.md
