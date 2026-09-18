---
name: chatgpt-worker
description: Delegate a coding task to ChatGPT Web, validate the resulting GitHub branch on a remote Linux environment over SSH, and iteratively send failures or review feedback back to the same ChatGPT conversation until validation passes or the iteration limit is reached.
---

# ChatGPT Worker

Use Antigravity as the orchestrator and reviewer. Use ChatGPT Web as the coding worker.

## Inputs to establish

Infer these from the current workspace and user request whenever possible. Do not ask for values that are already available.

- GitHub repository.
- Task description and acceptance criteria.
- Task branch. Prefer `chatgpt-worker/<short-task-name>`.
- Remote SSH host. Default to `CHATGPT_WORKER_HOST`, otherwise `ai-server`.
- Remote validation checkout/worktree path.
- Validation commands: tests, type checking, linting, build, or task-specific checks.
- Maximum repair iterations. Default to 5 unless the user specifies otherwise.

## Workflow

1. Inspect the local project context needed to formulate a precise coding task.
2. Use Antigravity's native browser to open ChatGPT Web. Reuse the same conversation throughout a task.
3. Tell ChatGPT exactly which GitHub repository and task branch to modify. Give acceptance criteria and relevant constraints. Instruct it to use its connected GitHub capability to make the changes and report the resulting commit SHA when finished.
4. Never provide ChatGPT Web with SSH keys, tokens, cookies, passwords, or unrelated secrets.
5. After ChatGPT reports completion, validate independently on Linux:
   - connect through SSH;
   - enter the designated validation checkout/worktree;
   - fetch the remote repository;
   - update/reset the validation worktree to the task branch as configured for that project;
   - record the tested commit SHA;
   - inspect the diff from the previous tested SHA when available;
   - run the configured validation commands.
6. Perform a semantic review in addition to mechanical tests. Check that the implementation satisfies the request, avoids unrelated changes, does not weaken tests merely to obtain a pass, and handles obvious failure paths.
7. If validation fails, send one concise feedback message to the SAME ChatGPT Web conversation containing:
   - tested commit SHA;
   - failing command(s);
   - relevant error/output excerpts;
   - specific semantic review findings;
   - a request to fix the problems in the same task branch and report the new commit SHA.
8. Fetch and validate again. Repeat until validation passes or the maximum iteration count is reached.
9. Do not merge automatically unless the user explicitly requests merging. A passing result means "ready for user/PR/merge review", not permission to merge.
10. Finish with a concise report: branch, final commit, iterations, commands run, pass/fail status, and any remaining concerns.

## Remote execution

Prefer the bundled helper when available:

```bash
bash scripts/remote.sh repo /path/to/worktree git status --short
bash scripts/remote.sh test /path/to/worktree 'pytest -q'
```

For multi-step synchronization, use explicit safe Git commands appropriate to the repository. Do not discard unrelated user work. A dedicated disposable validation worktree is strongly preferred.

## Feedback format

Keep repair messages compact. Include the smallest useful error excerpts rather than dumping entire logs. When a failure strongly indicates a source location, mention it, but let ChatGPT investigate the implementation.

## Stop conditions

Stop and report instead of continuing when:

- the maximum iteration count is reached;
- authentication or repository access is unavailable;
- the requested branch cannot be identified safely;
- validation would require a destructive or privileged operation that the user did not authorize;
- the task changes scope materially and requires a user decision.
