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

Remote projects may also define path mappings for storage mounted at different paths on Linux and macOS:

    [[remote.path_mappings]]
    remote = "/mnt/omv"
    local = "/Volumes/omv"

Treat these paths as the same underlying storage. When a remote job creates an image, video, audio file, log, report, or other artifact under a mapped remote prefix, translate it to the local path and inspect/read it directly from macOS when that is more convenient. Do not copy the file over SSH merely to inspect it if the mapped local mount is available.

Project configuration may also define the Git-backed communication runtime:

    [communication]
    runtime_dir = ".chatgpt-worker"
    retain_on_merge = false

The current design requires retain_on_merge = false: communication history lives on the task branch and should not be retained on the default branch when code is merged.

## Inputs to establish automatically

Infer these from the opened project, its Git metadata, .chatgpt-worker.toml, and the user request whenever possible:

- GitHub repository from git remote get-url origin.
- Task description and acceptance criteria.
- Task branch, using branch_prefix.
- Execution mode.
- Local or discovered remote validation repository.
- Validation commands.
- Remote-to-local path mappings, when configured.
- Maximum repair iterations.

Do not ask the user for values already discoverable from the project.

## Git-backed communication protocol

The authoritative Antigravity ↔ ChatGPT Web communication channel is Git on the task branch, not prose scraped from the browser UI.

For each task:

1. Create or select a dedicated task branch using branch_prefix.
2. Ensure the task branch contains the runtime directory (default `.chatgpt-worker/`).
3. Copy the canonical protocol from the installed plugin's `protocol/PROTOCOL.md` to `.chatgpt-worker/PROTOCOL.md` on the task branch.
4. Create one session under `.chatgpt-worker/sessions/<session-id>/`.
5. Append immutable request files under `requests/NNNN.md`.
6. Require ChatGPT Web to append the matching `responses/NNNN.json`.
7. Treat the Git response file as authoritative. Browser prose is only a wake-up/control signal.
8. Never create or maintain runtime communication files on the default branch.
9. On merge, omit/remove the runtime communication directory from the default branch because retain_on_merge is false. The task branch remains the audit trail.

Prefer the bundled protocol helper:

    "$PLUGIN_ROOT/scripts/protocol.py" init-session ...
    "$PLUGIN_ROOT/scripts/protocol.py" add-request ...
    "$PLUGIN_ROOT/scripts/protocol.py" check-response ...

Browser wake-up messages should be short and stable, for example:

    Continue the chatgpt-worker task.

    Repository: <owner/repo>
    Branch: <task-branch>
    Session: <session-id>
    Next request: <NNNN>

    Read .chatgpt-worker/PROTOCOL.md and the pending request file in the repository.
    Make the requested code changes, commit and push them, then write the corresponding response JSON file.

Do not parse the browser reply to determine completion. Fetch/pull the task branch and inspect the response JSON instead.

## Workflow

1. Run project discovery and verify the execution target is READY.
2. Inspect only the project context needed to formulate a precise coding task.
3. Create/select the dedicated task branch. Do not use the default branch for communication runtime files.
4. Initialize `.chatgpt-worker/` on that task branch, including `PROTOCOL.md`, session state, and request `0001.md`.
5. Commit and push the request/runtime files to the task branch.
6. Use Antigravity's native browser to open ChatGPT Web. Reuse the same conversation throughout the task.
7. Send only the compact wake-up message containing repository, branch, session ID, and request ID.
8. Wait by fetching/pulling the task branch until the corresponding response JSON appears. Do not use ChatGPT's browser prose as the completion signal.
9. Parse and validate the response JSON. Verify the declared commit exists and belongs to the task branch.
10. Independently fetch and validate the task branch in the configured execution environment.
11. Record the exact tested commit SHA and inspect the code diff.
12. Run every configured validation command and perform semantic review.
13. If validation or review fails, append the next immutable request file describing the tested commit, failing commands, concise errors, and review findings. Commit/push it, then send another compact wake-up message.
14. Repeat until validation passes or max_iterations is reached.
15. Mark the session completed on the task branch.
16. Do not merge automatically unless the user explicitly requests merging.
17. When merging code, keep runtime communication files off the default branch. Preserve the task branch as the Git audit trail.
18. Finish with a concise report: execution target, task branch, session ID, final commit, iterations, validation commands, pass/fail status, and remaining concerns.

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

## Remote artifact path mapping

When discovery returns path_mappings, interpret each pair as aliases for the same storage.

Example:

    /mnt/omv/resources/output/movie.mp4
    ->
    /Volumes/omv/resources/output/movie.mp4

If a validation command or remote job reports an artifact under a mapped remote prefix:

1. translate the longest matching remote prefix to its local prefix;
2. verify the local path exists before using it;
3. prefer local macOS inspection for images, video, audio, PDFs, generated reports, and other files when suitable;
4. keep command execution on the configured execution machine unless the task specifically requires otherwise;
5. if the local mount is unavailable, fall back to remote inspection or an explicit transfer rather than assuming the mapping is mounted.

The helper scripts/path_translate.py can translate an individual remote path using the project config.

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
