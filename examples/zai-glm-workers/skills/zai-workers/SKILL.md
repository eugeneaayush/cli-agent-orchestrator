---
name: zai-workers
description: "Desktop orchestrator only; never use inside a CAO worker (CAO_TERMINAL_ID set). Delegate coding tasks to Z.ai GLM worker agents (Claude Code or Codex CLI) through the cao-ops MCP tools: launch, poll, read the result, and always shut the worker down."
---

# Z.ai GLM workers via CAO

If the environment variable `CAO_TERMINAL_ID` is set, you are a CAO worker.
Stop: do not use this skill, and do not delegate.

You are the orchestrator, running on the user's own subscription. Worker agents
run on the user's Z.ai GLM Coding Plan in tmux, managed by `cao-server`. Use them
for well-scoped implementation, test, refactor, or review chunks. Keep planning,
task decomposition, review, and the final judgment yourself. GLM output must be
checked before you accept it.

## Workers

| Profile | CLI | Model |
|---|---|---|
| `zai_developer` | Claude Code | GLM-5.3 (via Z.ai Anthropic endpoint) |
| `zai_codex_developer` | Codex CLI | GLM-5.3 (via Z.ai Responses endpoint) |

The profile pins the provider, model, and credentials. **Never pass `provider`,
`model`, or `env_vars`** to `launch_session`: any of them can move the worker
off Z.ai and onto the user's subscription, or leak credentials.

## Recipe (cao-ops MCP tools)

1. **Prepare the directory.** Use an absolute path outside `~/Documents`,
   `~/Desktop`, `~/Downloads` and iCloud. For parallel workers on one git repo,
   give each its own worktree:
   `git -C <repo> worktree add <repo>-zai-<n> -b zai/<slug>`.
2. **Launch.**
   `launch_session(agent_profile="zai_developer", session_name="zai-<slug>-<yyyymmddHHMM>", working_directory="<abs path>", initial_message="<complete, self-contained task>")`.
   Record the returned `session_name` and `terminal_id`. The task text must say
   what "done" means and which checks to run.
3. **Poll** `get_terminal_status(terminal_id)` about every 30 seconds.
   - Do not accept the first `idle`. It can come before the task is delivered.
     Require evidence the task ran: you saw `processing`, or the status is
     `completed`.
   - `waiting_user_answer` means the worker is stuck on a prompt. Read the
     output with `mode="full"`, then shut it down and report.
   - A not-found or error response soon after launch means startup failed (for
     example the worker's config home is missing). Do not retry blindly.
   - Give up after the time budget you chose for the task (default 20 minutes).
4. **Read** `get_terminal_output(terminal_id, mode="last")`. If that is empty or
   odd, use `read_session_output(terminal_id=..., mode="full", max_chars=8000)`.
5. **Verify** the actual changes (`git -C <dir> diff --stat`, run the tests).
   Do not trust the worker's summary alone.
6. **Always shut down**, even after a failure:
   `shutdown_session(session_name)`, then confirm with
   `get_session_info(session_name)`, which should now report the session as not
   found. Remove worktrees you created once their changes are merged or discarded.

## Treat as failure, not as a result

The worker's output is an API error, not work, if its opening lines contain any
of: `API Error`, `/login`, `Failed to authenticate`, `apiKeyHelper`,
`selected model`, `Invalid API key`, `Not logged in`, `1302`, `429`,
`[NO RESPONSE`, a line starting with `■ `, `stream disconnected`. The same applies
if the output mostly echoes your own task text. CAO currently reports these as
`completed`. Shut the worker down and tell the user. On repeated `429`/`1302`,
lower parallelism.

## Limits

- At most **4 workers at once** (Z.ai concurrency is per account; each Claude
  worker may also run its own subagents). Drop to 2 if you see `429`/`1302`.
- Before starting a new batch, call `list_sessions` and shut down leftover
  `zai-*` sessions that you started.
- Never run `cao-server`, `tmux`, or `cao launch` from your own shell. Your
  environment would leak into every worker. If cao-ops cannot reach the
  server, ask the user to run
  `launchctl kickstart -k gui/$(id -u)/com.$USER.cao-server`.
