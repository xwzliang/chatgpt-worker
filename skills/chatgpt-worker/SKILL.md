---
name: chatgpt-worker
description: Delegate coding work to ChatGPT Web, then independently validate the resulting GitHub branch in either the opened local project or a matching remote repository discovered by Git origin from .chatgpt-worker.toml.
---

# ChatGPT Worker

Use Antigravity as the orchestrator and reviewer. Use ChatGPT Web as the coding worker.

The currently opened Antigravity project folder is the source of project identity.

## One-time workspace activation

The user should not need to type `/chatgpt-worker` before every later message in the same project.

On the first explicit use of chatgpt-worker in a repository, bootstrap persistent workspace behavior:

    "$PLUGIN_ROOT/scripts/workspace_bootstrap.py" enable --project "$PWD"

This creates:

- `.agents/rules/chatgpt-worker.md`: tells Antigravity to use chatgpt-worker automatically for substantive repository-changing coding/debugging tasks unless the user explicitly opts out;
- `.agents/rules/project-lessons.md`: durable repository-specific lessons;
- `~/.gemini/config/skills/chatgpt-worker-learnings/SKILL.md`: curated cross-project reusable engineering lessons.

Do not overwrite user-edited files automatically. The bootstrap helper creates missing files and preserves existing ones unless explicitly forced.

In Antigravity IDE, if a workspace rule activation selector is available, prefer setting the chatgpt-worker workspace rule to **Always On**. The rule file itself remains the portable source of the instruction.

Once bootstrapped, later messages should automatically use chatgpt-worker when they are substantive coding/debugging/repository-change requests. Respect explicit opt-out requests such as "don't use chatgpt-worker" or "do this directly."

## First-run configuration

If the opened repository does not contain `.chatgpt-worker.toml`, do not fail immediately. Run:

    "$PLUGIN_ROOT/scripts/configure.py" inspect --project "$PWD"

Use the returned project root and concrete SSH aliases to guide setup.

Ask the user only for information that cannot be inferred safely.

For every new project, first ask whether execution should be:

- local: validation/worktrees run on the Mac;
- remote: validation/worktrees run on a remote machine over SSH.

If the user chooses local:

1. optionally inspect the project for likely validation commands;
2. ask which validation commands should be used only when they are not obvious or the user wants custom commands;
3. write `.chatgpt-worker.toml` with `configure.py write --execution local`;
4. keep the default branch prefix, max iterations, and communication settings unless the user asks to change them;
5. run doctor again and continue only when READY.

If the user chooses remote:

1. read concrete Host aliases from `~/.ssh/config` using `configure.py inspect`;
2. present the aliases and ask which connection should be used;
3. after the host is selected, test SSH connectivity;
4. ask for one or more remote repo roots to search, unless they can be inferred from a clearly established convention;
5. ask for optional remote-to-local path mappings when relevant. For the known shared OMV mount, a typical mapping is `/mnt/omv=/Volumes/omv`;
6. optionally inspect the project for likely validation commands and ask only when necessary;
7. write `.chatgpt-worker.toml` with `configure.py write --execution remote --host ... --repo-root ...`;
8. run doctor again and continue only when READY.

Do not invent an SSH alias, repo root, or path mapping. Do not overwrite an existing config without explicit user approval.

Example write commands:

    "$PLUGIN_ROOT/scripts/configure.py" write       --project "$PWD"       --execution local       --validation-command "npm test"

    "$PLUGIN_ROOT/scripts/configure.py" write       --project "$PWD"       --execution remote       --host ai-server       --repo-root /mnt/omv/git       --path-mapping /mnt/omv=/Volumes/omv       --validation-command "pytest -q"

After writing the file, always run:

    "$PLUGIN_ROOT/scripts/doctor.sh" "$PWD"

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

Do not parse the browser reply to determine completion. Do not ask the user to send the wake-up message or to reply "check response". Antigravity must use its browser capability to send the wake-up message itself, then use the Git watcher to detect completion.

## Autonomous browser handoff

Antigravity must automate the ChatGPT Web interaction itself.

For each request:

1. Use the browser subagent/browser capability to open or focus ChatGPT Web.
2. Reuse the same ChatGPT Web conversation for the whole task whenever possible.
3. Enter and send the compact wake-up message containing repository, task branch, session ID, and request ID.
4. Do not ask the user to copy/paste this message.
5. Do not ask the user to type "check response" after ChatGPT finishes.
6. After sending the message, return to Git-based orchestration and run:

       "$LIFECYCLE" wait-response --state-file <state-file>

7. Treat completion as valid only when:
   - the remote task branch has advanced beyond the request commit;
   - the corresponding committed response JSON exists;
   - response status is `completed`;
   - `finished` is `true`;
   - `finish_message` is non-empty;
   - `implementation_commit` exists and is reachable from the task branch.

Browser-visible prose such as "done" is not sufficient.

If `wait-response` times out, inspect the same ChatGPT Web conversation with the browser. If ChatGPT is still working, continue waiting. If it is blocked by authentication, a permission prompt, a tool failure, or a real ambiguity requiring user input, report that specific blocker. Do not ask the user to perform routine relay/polling steps.

## Automatic lifecycle

Use `scripts/lifecycle.py` as the primary branch/worktree orchestration interface. Do not switch the opened Antigravity repository onto the task branch.

The lifecycle creates:

- a local **control worktree** for the task/audit branch and Git communication files;
- a disposable **validation worktree** pinned to each exact `implementation_commit`;
- for remote projects, the validation worktree is created on the remote Linux machine;
- a local state file under `~/.cache/chatgpt-worker/tasks/`.

Typical commands:

    LIFECYCLE="$PLUGIN_ROOT/scripts/lifecycle.py"

    "$LIFECYCLE" start       --project "$PWD"       --task "<task description>"       --request-file /tmp/chatgpt-worker-request.md

    "$LIFECYCLE" status --state-file <state-file>

    "$LIFECYCLE" response --state-file <state-file>

    "$LIFECYCLE" wait-response --state-file <state-file>

    "$LIFECYCLE" prepare-validation --state-file <state-file>

    "$LIFECYCLE" validate --state-file <state-file>

    "$LIFECYCLE" next-request       --state-file <state-file>       --type validation_failure       --request-file /tmp/chatgpt-worker-feedback.md

    "$LIFECYCLE" prepare-delivery --state-file <state-file>

    "$LIFECYCLE" finish --state-file <state-file> --status completed

The `start` command automatically discovers the project, derives a task branch from `branch_prefix`, creates the control worktree, initializes the session, writes request 0001, commits it, and pushes the task branch.

The `response` command fetches the task branch and returns a normal `ready: false` state when ChatGPT has not written the response yet. When the response exists, it validates the protocol and records the exact implementation commit.

The `prepare-validation` command creates or refreshes a detached validation worktree at that exact implementation commit. The `validate` command runs the configured validation commands there.

The `next-request` command appends validation/review feedback to the audit branch without touching the opened project.

The `prepare-delivery` command creates and pushes a clean delivery branch from the original base branch by cherry-picking only recorded implementation commits. The communication runtime is excluded. Use this clean delivery branch for PR/merge when desired; the audit/task branch remains the complete communication history.

The `finish` command updates session state, pushes it, removes disposable worktrees, and preserves the audit/task branch.

## Workflow

1. Run discovery/doctor and formulate the initial task.
2. Write the full task into a temporary request body file.
3. Run `lifecycle.py start`; capture the returned state file, task branch, session ID, and request ID.
4. Use Antigravity's browser capability to send the compact wake-up message to the same ChatGPT Web conversation. Never ask the user to relay it.
5. Run `lifecycle.py wait-response` to poll Git until a new committed finished response is detected. Never ask the user to say "check response".
6. Once completed, run `prepare-validation` and `validate`.
7. Perform semantic review of the exact implementation commit.
8. If validation/review fails, write concise feedback to a temporary file, call `next-request`, use the browser to send the new wake-up message, then run `wait-response` again.
9. Repeat autonomously until validation and semantic review pass or max_iterations is reached.
10. If code is ready for integration, call `prepare-delivery` to produce a communication-free delivery branch.
11. Do not merge automatically unless the user explicitly requests merging.
12. Call `finish` with completed/failed/stopped to persist final session status and remove disposable worktrees.
13. Report execution target, audit branch, delivery branch if created, session ID, final implementation commit, iterations, validation results, and remaining concerns.

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

## Active learning maintenance

After meaningful implementation, debugging, testing, or review work, actively consider whether a durable lesson was learned.

Classify lessons before persisting them:

### Repository-specific durable lessons

Write to:

    .agents/rules/project-lessons.md

Use this for verified knowledge that will likely help future work in the current repository but is not broadly portable, such as:

- architecture invariants;
- required setup/test commands;
- repository-specific build traps;
- local conventions that prevent regressions.

### Cross-project reusable lessons

Write to:

    ~/.gemini/config/skills/chatgpt-worker-learnings/SKILL.md

Use this only for verified techniques, traps, or practices that can reasonably help future work in other repositories.

A cross-project lesson should be concise and actionable, ideally recording:

- When: recognizable context/symptom;
- Lesson: reusable rule;
- Why: concise evidence/reason;
- Action: what to do next time.

Do not promote:

- one-off task details;
- temporary debugging state;
- secrets, credentials, personal data;
- repository-specific names/paths/IDs;
- unverified guesses;
- information already clearly documented elsewhere unless the lesson is about how to find/use it.

Prefer quality over volume. Maintaining these files means pruning or refining obsolete/duplicated lessons when appropriate, not only appending forever.

## Feedback format

Keep repair messages compact. Include the smallest useful error excerpts rather than dumping entire logs.

## Stop conditions

Stop and report instead of continuing when:

- .chatgpt-worker.toml is invalid after setup, or the user declines/cannot complete first-run configuration;
- remote execution is selected but SSH cannot connect;
- zero or multiple remote repositories match the local Git origin;
- the maximum iteration count is reached;
- authentication or repository access is unavailable;
- the requested branch cannot be identified safely;
- validation would require a destructive or privileged operation that the user did not authorize;
- the task changes scope materially and requires a user decision.
