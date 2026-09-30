# Z.ai GLM workers behind subscription orchestrators

Run coding **workers** on a [Z.ai GLM Coding Plan](https://docs.z.ai/devpack/overview) while
the **orchestrators** (the Claude Code desktop app and the Codex desktop app) stay on your own
Claude and ChatGPT subscriptions.

```
Claude desktop app (your Claude login)  ─┐   cao-ops MCP    ┌─ CLAUDE_CONFIG_DIR=~/.claude-zai claude …  → api.z.ai/api/anthropic
Codex desktop app  (your ChatGPT login) ─┴─► cao-server ────┴─ CODEX_HOME=~/.codex-zai codex …         → api.z.ai/api/v1
                                            (launchd, clean env)    each CLI reads the key from the macOS Keychain
```

Each worker runs a real `claude` or `codex` CLI (the tools the Z.ai plan supports) under its **own
config home**, selected per profile with [`claudeConfig.configDir`](../../docs/claude-code.md#per-agent-config-directory)
and [`codexHome`](../../docs/codex-cli.md#per-agent-codex-home). Those homes point at Z.ai and
contain no Claude or ChatGPT login. A misconfigured worker therefore fails, instead of running
on, or sending, your own subscription credentials.

> Do not point your global `~/.claude/settings.json` or `~/.codex/config.toml` at Z.ai
> (`npx @z_ai/coding-helper` does this). That moves the orchestrators themselves onto GLM, or,
> for the Claude desktop app, which always uses its own login, applies GLM model names to
> Anthropic requests so they fail. See [Undo a global Z.ai setup](#undo-a-global-zai-setup).

## Files

| File | Purpose |
|---|---|
| `setup.sh` | Creates `~/.claude-zai` and `~/.codex-zai` (never overwrites) |
| `zai_developer.md` | Worker profile: Claude Code CLI on GLM-5.3 |
| `zai_codex_developer.md` | Worker profile: Codex CLI on GLM-5.3 |
| `skills/zai-workers/SKILL.md` | Orchestrator skill: launch, poll, verify and shut down workers through cao-ops |

## Setup (macOS)

1. **Install tools and CAO.** Use a regular install, not `--editable` from a temporary checkout:

   ```bash
   brew install tmux uv
   uv tool install cli-agent-orchestrator   # or: uv tool install <path-to-a-stable-checkout>
   ```

2. **Store the Z.ai API key in the Keychain.** Run this in Terminal. It prompts for the key, so the
   key never lands in your shell history:

   ```bash
   security add-generic-password -a "$USER" -s zai-coding-plan -U -w
   ```

3. **Create the worker homes:**

   ```bash
   sh examples/zai-glm-workers/setup.sh
   ```

   `~/.claude-zai/settings.json` sets the Z.ai endpoint, maps `opus`/`sonnet`/`haiku` to
   `glm-5.3[1m]`/`glm-5.3-flash[1m]`, and reads the key with an `apiKeyHelper`.
   `~/.codex-zai/config.toml` defines a `ZAI` model provider whose `auth` command reads the key.
   Neither file contains the key.

4. **Run `cao-server` as a LaunchAgent** so that it, and the tmux server it starts, have a clean
   environment. Every tmux pane inherits the tmux server's global environment (see
   [docs/tmux.md](../../docs/tmux.md)). launchd does not expand `~` or `$HOME`, so write absolute
   paths. Replace `you` with your user name:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key><string>com.you.cao-server</string>
     <key>ProgramArguments</key><array><string>/Users/you/.local/bin/cao-server</string></array>
     <key>WorkingDirectory</key><string>/Users/you</string>
     <key>EnvironmentVariables</key>
     <dict>
       <key>PATH</key><string>/Users/you/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
       <key>LANG</key><string>en_US.UTF-8</string>
       <key>PYTHONUNBUFFERED</key><string>1</string>
     </dict>
     <key>ProcessType</key><string>Interactive</string>
     <key>RunAtLoad</key><true/>
     <key>KeepAlive</key><true/>
     <key>StandardOutPath</key><string>/Users/you/Library/Logs/cao-server.log</string>
     <key>StandardErrorPath</key><string>/Users/you/Library/Logs/cao-server.log</string>
   </dict>
   </plist>
   ```

   Save it as `~/Library/LaunchAgents/com.you.cao-server.plist`, then:

   ```bash
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.you.cao-server.plist
   curl -sf http://localhost:9889/sessions && echo " cao-server OK"
   ```

5. **Install the worker profiles:**

   ```bash
   cao install examples/zai-glm-workers/zai_developer.md
   cao install examples/zai-glm-workers/zai_codex_developer.md
   ```

6. **Connect the orchestrators** to CAO's external control plane, `cao-ops-mcp-server`:

   - Claude desktop app / Claude Code:

     ```bash
     claude mcp add -s user cao-ops -- /Users/you/.local/bin/cao-ops-mcp-server
     ```

   - Codex desktop app / Codex CLI, in `~/.codex/config.toml` (timeouts must be floats):

     ```toml
     [mcp_servers.cao-ops]
     command = "/Users/you/.local/bin/cao-ops-mcp-server"
     startup_timeout_sec = 30.0
     tool_timeout_sec = 330.0
     ```

   - Install the orchestrator skill for both apps:

     ```bash
     mkdir -p ~/.claude/skills ~/.codex/skills
     cp -R examples/zai-glm-workers/skills/zai-workers ~/.claude/skills/
     cp -R examples/zai-glm-workers/skills/zai-workers ~/.codex/skills/
     ```

   Workers never see this skill or these MCP servers, because they run under their own config homes.

7. Restart both desktop apps.

Use cao-ops (`launch_session`, then poll, read, and `shutdown_session`) rather than the in-session
`handoff`/`assign` tools. Those tools need `CAO_TERMINAL_ID`, which a desktop app does not have:
`assign` and a `handoff` to a Codex worker always fail, and a blocking `handoff` stalls the desktop
app's turn.

## Verify

```bash
# Worker CLIs on Z.ai, in a clean environment
env -i HOME="$HOME" USER="$USER" PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin" \
  CLAUDE_CONFIG_DIR="$HOME/.claude-zai" claude -p "Reply with OK" --output-format json
env -i HOME="$HOME" USER="$USER" PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin" \
  CODEX_HOME="$HOME/.codex-zai" codex exec --skip-git-repo-check "Reply with OK"

# A worker through CAO (the profile pins the provider; do not pass --provider)
mkdir -p ~/zai-smoke
cao launch --agents zai_developer --headless --auto-approve --session-name zai-smoke \
  --working-directory ~/zai-smoke "Create hello.txt containing hi"

# No provider credentials or routing in the tmux global environment
tmux show-environment -g | cut -d= -f1 | grep -E '^(ANTHROPIC|CLAUDE|CODEX|OPENAI|Z_AI|API_TIMEOUT)' || echo clean

cao shutdown --session cao-zai-smoke
```

Then ask an orchestrator: *"Use zai-workers to have zai_developer create ~/zai-smoke/notes.md."*
Usage should appear on the Z.ai dashboard, not on your Claude or ChatGPT account.

## Operations

- **Watch a worker:** `tmux attach -r -t <session_name>` (read-only) from Terminal.
- **Restart the server** (for example after reinstalling CAO):
  `launchctl kickstart -k gui/$(id -u)/com.you.cao-server`.
- **Stop everything:** `cao shutdown --all`, then
  `launchctl bootout gui/$(id -u)/com.you.cao-server`, and optionally `tmux kill-server`. tmux keeps
  running after cao-server stops.
- **Logs:** `~/.aws/cli-agent-orchestrator/logs/` (server) and `~/Library/Logs/cao-server.log`.

## Security notes

- The key is read at run time by `/usr/bin/security`. It is not stored in profiles, CAO
  configuration, tmux arguments or terminal logs. Never put keys or `${VAR}` placeholders for keys
  in a profile.
- Workers run with approvals bypassed (`--dangerously-skip-permissions` / `--yolo`), on a
  third-party model. The `Read` deny rules in `~/.claude-zai/settings.json` do not stop a shell
  command such as `cat`. Treat anything a worker can read, in its working directory and your home
  directory, as visible to Z.ai. Keep secrets out of worker working directories.
- Workers cannot delegate: the Claude worker's settings deny CAO's `handoff`/`assign`/workflow
  tools, and the Codex worker has no CAO MCP server.
- On macOS, keep worker repositories outside `~/Documents`, `~/Desktop`, `~/Downloads` and
  iCloud Drive. Privacy protection may block a launchd-hosted process there.
- The Z.ai plan terms allow use only inside supported coding tools (Claude Code and Codex CLI are
  supported) and limit concurrency per account. The orchestrator skill caps parallel workers at 4.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `launch_session` succeeds, then the terminal is not found | Startup failed. A missing `~/.claude-zai` / `~/.codex-zai` makes the launch fail closed. Check the server log. |
| Worker output: `Your apiKeyHelper script is failing` / `Not logged in` | The Keychain item is missing or named differently. Re-run step 2 and compare with `setup.sh`'s service and account. |
| Output contains `429` or `1302` | Z.ai concurrency limit. Run fewer workers at once. |
| Codex worker: `Model provider ZAI not found` | `~/.codex-zai/config.toml` is missing the `[model_providers.ZAI]` table. |
| Worker stuck at a first-run screen | Run `CLAUDE_CONFIG_DIR=~/.claude-zai claude` (or `CODEX_HOME=~/.codex-zai codex`) once interactively in Terminal. |

## Undo a global Z.ai setup

If `npx @z_ai/coding-helper` configured Z.ai globally:

- `~/.claude/settings.json`: delete the Z.ai keys in `env` (`ANTHROPIC_AUTH_TOKEN`,
  `ANTHROPIC_BASE_URL`, `ANTHROPIC_DEFAULT_*_MODEL`, `API_TIMEOUT_MS`,
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`). Then run
  `claude plugin uninstall <name>@zai-coding-plugins` for each installed GLM helper (one per
  command), `claude plugin marketplace remove zai-coding-plugins`, and
  `claude mcp remove -s user <name>` for the Z.ai MCP servers it added.
- `~/.codex/config.toml`: remove the top-level `model_provider = "ZAI"` and `model_catalog_json`,
  and the `[mcp_servers.zai-mcp-server]` table. Start new threads in the Codex app: existing threads
  keep the provider they were created with.
- Rotate the API key if it was ever stored in plain text or shared.
