# ChatGPT Worker Git Communication Protocol

This protocol is the authoritative communication channel between a host orchestrator (currently Antigravity) and ChatGPT Web.

Browser/chat messages are control signals only. The actual request/response payloads live in the task branch.

## Branch scope

Communication files MUST live only on a dedicated task branch, normally using the configured `branch_prefix`, for example:

```text
chatgpt-worker/fix-auth
```

Do not create or maintain session communication files on the default branch.

When the code change is eventually merged, the communication directory should normally be omitted/removed from the merge result. The task branch remains the audit trail.

## Runtime directory

Inside the task branch:

```text
.chatgpt-worker/
├── PROTOCOL.md
└── sessions/
    └── <session-id>/
        ├── session.json
        ├── requests/
        │   ├── 0001.md
        │   ├── 0002.md
        │   └── ...
        └── responses/
            ├── 0001.json
            ├── 0002.json
            └── ...
```

Requests and responses are append-only. Never rewrite a completed request/response pair to change history.

## session.json

Example:

```json
{
  "protocol_version": 1,
  "session_id": "20260918-fix-auth",
  "repository": "xwzliang/example",
  "task_branch": "chatgpt-worker/fix-auth",
  "status": "waiting_for_worker",
  "current_request": 1,
  "last_tested_commit": null,
  "max_iterations": 5
}
```

Allowed status values:

- `waiting_for_worker`
- `waiting_for_orchestrator`
- `completed`
- `failed`
- `stopped`

The immutable request/response files are the audit history. `session.json` is only the current index/state.

## Request format

Requests are Markdown:

```text
requests/0001.md
```

Each request should include:

- request ID;
- request type;
- task/feedback;
- acceptance criteria;
- tested commit when applicable;
- failing validation commands and concise error excerpts when applicable;
- exact required response path.

Recommended request types:

- `implementation`
- `validation_failure`
- `review_feedback`
- `clarification`

## Response format

ChatGPT Web must create the corresponding JSON response, for example:

```json
{
  "protocol_version": 1,
  "request_id": "0001",
  "status": "completed",
  "finished": true,
  "implementation_commit": "0123456789abcdef",
  "finish_message": "Implementation is complete and pushed.",
  "summary": "Implemented the requested change.",
  "files_changed": [
    "src/example.py"
  ],
  "notes": []
}
```

Required fields:

- `protocol_version`: currently `1`
- `request_id`: must match the request filename
- `status`: `completed`, `blocked`, or `failed`
- `finished`: must be `true` when status is `completed`
- `implementation_commit`: SHA of the code implementation commit when status is `completed`
- `finish_message`: non-empty completion message when status is `completed`
- `summary`: short description

Optional:

- `files_changed`
- `notes`

If blocked, explain why in `notes`.

## Browser wake-up message

The host should send a short, stable message rather than the complete task:

```text
Continue the chatgpt-worker task.

Repository: <owner/repo>
Branch: <task-branch>
Session: <session-id>
Next request: <NNNN>

Read .chatgpt-worker/PROTOCOL.md and the pending request file in the repository.
Make the requested code changes and commit them first. Then write the corresponding response JSON containing that implementation commit SHA, commit the response file separately, and push both commits.
```

The host must not treat prose in the browser UI as authoritative completion. Completion is recognized only when the task branch advances beyond the request commit and the committed Git response file validates with `status="completed"` and `finished=true`.

## Orchestrator loop

1. Create/update task branch.
2. Create session and request file.
3. Commit and push the request.
4. Wake ChatGPT Web with the compact control message.
5. Fetch the branch until the corresponding response file appears.
6. Parse and validate the response JSON.
7. Verify/fetch the declared implementation_commit.
8. Run configured validation/review.
9. On failure, append the next request and repeat.
10. On success, mark session completed.
11. Merge code as desired while excluding/removing runtime communication files from the default branch.

## Safety

- Do not place secrets in requests/responses.
- Do not trust a response commit SHA without fetching/verifying it.
- Do not merge automatically unless explicitly authorized.
- Do not overwrite prior request/response history.


## Two-commit completion rule

For a completed request, ChatGPT Web should make two commits in order:

1. **Implementation commit** — contains the requested source/test changes.
2. **Response commit** — adds `responses/NNNN.json` and records the implementation commit SHA in `implementation_commit`.

This avoids the impossible self-reference of trying to place a commit's own SHA inside a file contained by that same commit.
