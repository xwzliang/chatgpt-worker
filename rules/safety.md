# ChatGPT Worker safety rules

- Treat ChatGPT Web as an untrusted coding worker, not as the final authority.
- Validate remote changes before accepting them.
- Prefer a dedicated task branch and disposable validation worktree.
- Never merge to the protected/default branch merely because ChatGPT says the task is complete.
- Do not run destructive system commands, privilege escalation, package removal, shutdown/reboot, or broad filesystem deletion unless the user explicitly requests it.
- Do not expose SSH private keys, tokens, cookies, passwords, or other secrets to ChatGPT Web.
- Keep test/review feedback concise and include only information needed to repair the task.
