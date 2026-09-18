---
name: chatgpt-worker
description: Delegate coding work to ChatGPT Web, then independently validate the resulting GitHub branch in either the opened local project or a matching remote repository discovered by Git origin from .chatgpt-worker.toml.
---

# ChatGPT Worker

Use Antigravity as the orchestrator and reviewer. Use ChatGPT Web as the coding worker.

The currently opened Antigravity project folder is the source of project identity.

## Mandatory project discovery

Before delegating a task, locate the Git root of the opened project and read .chatgpt-worker.toml from that repository root.

Prefer the bundled helpers:

    PLUGIN_ROOT="$HOME/.gemini/config/plugins/chatgpt-worker"
    "$PLUGIN_ROOT/scripts/doctor.sh" "$PWD"
    "$PLUGIN_ROOT/scripts/discover.py" --project "$PWD" --json

Do not guess the execution target when discovery is available.

The configuration selects one mode:

- execution = "local": validate in the opened local repository/worktree on the Mac.
- execution = "remote": use the configured SSH host and repo_roots; discover the remote repository by matching its normalized Git origin to the opened local repository's normalized origin.

For remote mode, never select a repository only because its directory name matches. Git-origin equality is the identity check. If zero or multiple matching remote repositories are found, stop and report the discovery error.

## Configuration

Local project example:

    execution = "local"
    branch_prefix = "chatgpt-worker/"
    max_iterations = 5

    [validation]
    commands = [
      "npm run typecheck",
      "npm test",
      "npm run build",
    ]

Remote project example:

    execution = "remote"
    branch_prefix = "chatgpt-worker/"
    max_iterations = 5

    [remote]
    host = "ai-server"
    repo_roots = [
      "/mnt/omv/git",
      "/home/broliang/git",
    ]

    [validation]
    commands = [
      "pytest -q",
      "ruff check .",
    ]

The SSH alias itself belongs in ~/.ssh/config, not in the repository configuration.

## Inputs to establish automatically

Infer these from the opened project, its Git metadata, .chatgpt-worker.toml, and the user request whenever possible:

- GitHub repository from git remote get-url origin.
- Task description and acceptance criteria.
- Task branch, using branch_prefix.
- Execution mode.
- Local or discovered remote validation repository.
- Validation commands.
- Maximum repair iterations.

Do not ask the user for values already discoverable from the project.

## Workflow

1. Run project discovery and verify the execution target is READY.
2. Inspect only the project context needed to formulate a precise coding task.
3. Use Antigravity's native browser to open ChatGPT Web. Reuse the same conversation throughout the task.
4. Tell ChatGPT exactly which GitHub repository and task branch to modify. Give acceptance criteria and relevant constraints. Instruct it to use its connected GitHub capability to make the changes and report the resulting commit SHA when finished.
5. Never provide ChatGPT Web with SSH keys, tokens, cookies, passwords, or unrelated secrets.
6. After ChatGPT reports completion, independently fetch and validate the task branch in the configured execution environment.
7. Record the exact tested commit SHA and inspect the diff from the previous tested SHA when available.
8. Run every configured validation command.
9. Perform a semantic review in addition to mechanical tests. Check that the implementation satisfies the request, avoids unrelated changes, does not weaken tests merely to obtain a pass, and handles obvious failure paths.
10. If validation fails, send one concise feedback message to the SAME ChatGPT Web conversation containing the tested commit SHA, failing commands, relevant error excerpts, review findings, and a request to fix the same task branch.
11. Fetch and validate again. Repeat until validation passes or max_iterations is reached.
12. Do not merge automatically unless the user explicitly requests merging.
13. Finish with a concise report: execution target, branch, final commit, iterations, commands run, pass/fail status, and remaining concerns.

## Local execution

When execution = "local", the opened repository is the validation source repository.

Prefer a disposable task worktree instead of changing the user's opened working tree. Do not discard local uncommitted work.

Default worktree root:

    ~/.cache/chatgpt-worker/worktrees/<repo>/<task>

Fetch the remote branch, create or refresh the disposable worktree, and run validation there.

## Remote execution

When execution = "remote", use target_host and target_repo returned by discover.py.

Prefer the bundled SSH helper:

    bash "$PLUGIN_ROOT/scripts/remote.sh" --host <host> repo <target_repo> git status --short

Use a disposable validation worktree. Do not alter unrelated work in the normal remote checkout.

Before using a remote candidate, discovery must verify that its normalized Git origin equals the opened local project's normalized Git origin.

## Feedback format

Keep repair messages compact. Include the smallest useful error excerpts rather than dumping entire logs.

## Stop conditions

Stop and report instead of continuing when:

- .chatgpt-worker.toml is missing or invalid;
- remote execution is selected but SSH cannot connect;
- zero or multiple remote repositories match the local Git origin;
- the maximum iteration count is reached;
- authentication or repository access is unavailable;
- the requested branch cannot be identified safely;
- validation would require a destructive or privileged operation that the user did not authorize;
- the task changes scope materially and requires a user decision.
