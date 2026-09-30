#!/bin/sh
# Create isolated Claude Code and Codex config homes for Z.ai GLM workers.
#
#   ~/.claude-zai  -> CLAUDE_CONFIG_DIR for the zai_developer profile
#   ~/.codex-zai   -> CODEX_HOME for the zai_codex_developer profile
#
# Both read the Z.ai API key at run time from the macOS Keychain; no key is
# written to disk. Existing files are never overwritten. Re-run safely.
#
# Overridable: ZAI_KEYCHAIN_SERVICE (default zai-coding-plan),
#              CLAUDE_ZAI_DIR (default ~/.claude-zai), CODEX_ZAI_DIR (default ~/.codex-zai)
set -eu

SERVICE="${ZAI_KEYCHAIN_SERVICE:-zai-coding-plan}"
ACCOUNT="$(id -un)"
CLAUDE_DIR="${CLAUDE_ZAI_DIR:-$HOME/.claude-zai}"
CODEX_DIR="${CODEX_ZAI_DIR:-$HOME/.codex-zai}"

if [ ! -x /usr/bin/security ]; then
  echo "error: /usr/bin/security not found (this script targets macOS Keychain)" >&2
  exit 1
fi

case "$SERVICE$ACCOUNT" in
  *\"*|*\\*) echo "error: keychain service/account must not contain quotes or backslashes" >&2; exit 1 ;;
esac

# write_new PATH: write stdin to PATH (mode 0600) unless PATH already exists.
write_new() {
  if [ -e "$1" ]; then
    echo "exists, left unchanged: $1"
    cat >/dev/null
  else
    (umask 077 && cat >"$1")
    echo "created: $1"
  fi
}

mkdir -p "$CLAUDE_DIR" "$CODEX_DIR"
chmod 700 "$CLAUDE_DIR" "$CODEX_DIR"

# --- Claude Code worker home -------------------------------------------------
# apiKeyHelper prints the key; Claude Code sends it as a Bearer token to
# ANTHROPIC_BASE_URL. The blank ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY values
# neutralize any copies leaked into the environment (they would outrank the
# helper). The deny rules stop GLM workers from delegating to other CAO workers
# and from reading other tools' credential files with the Read tool.
write_new "$CLAUDE_DIR/settings.json" <<EOF
{
  "apiKeyHelper": "/usr/bin/security find-generic-password -a $ACCOUNT -s $SERVICE -w",
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "",
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.3[1m]",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.3[1m]",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5.3-flash[1m]",
    "API_TIMEOUT_MS": "3000000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "1000000"
  },
  "skipDangerousModePermissionPrompt": true,
  "permissions": {
    "deny": [
      "mcp__cao-mcp-server__handoff",
      "mcp__cao-mcp-server__assign",
      "mcp__cao-mcp-server__assign_elastic",
      "mcp__cao-mcp-server__workflow_run",
      "mcp__cao-mcp-server__workflow_start",
      "mcp__cao-mcp-server__workflow_resume",
      "Read(~/.claude/**)",
      "Read(~/.claude.json)",
      "Read(~/.codex/**)",
      "Read(~/.aws/**)",
      "Read(~/.ssh/**)",
      "Read(~/.chelper/**)"
    ]
  }
}
EOF

# Skip first-run onboarding (theme picker / login screen) that would otherwise
# block the tmux pane. Deliberately no oauthAccount: this home has no login.
write_new "$CLAUDE_DIR/.claude.json" <<'EOF'
{
  "hasCompletedOnboarding": true
}
EOF

# --- Codex worker home ---------------------------------------------------------
# [model_providers.ZAI.auth] runs the command to obtain the bearer token; it
# cannot be combined with env_key / experimental_bearer_token /
# requires_openai_auth, and it has no fallback to a ChatGPT login.
write_new "$CODEX_DIR/config.toml" <<EOF
model = "glm-5.3"
model_provider = "ZAI"
model_reasoning_effort = "high"
model_catalog_json = "$CODEX_DIR/models.json"
check_for_update_on_startup = false

[model_providers.ZAI]
name = "Z.ai GLM Coding Plan"
base_url = "https://api.z.ai/api/v1"
wire_api = "responses"

[model_providers.ZAI.auth]
command = "/usr/bin/security"
args = ["find-generic-password", "-a", "$ACCOUNT", "-s", "$SERVICE", "-w"]
EOF

# Model catalog for Codex, per Z.ai's Codex setup guide.
write_new "$CODEX_DIR/models.json" <<'EOF'
{
  "models": [
    {
      "slug": "glm-5.3",
      "display_name": "glm-5.3",
      "description": "Z.ai GLM-5.3",
      "default_reasoning_level": "high",
      "supported_reasoning_levels": [
        { "effort": "low", "description": "Light reasoning" },
        { "effort": "high", "description": "Enhanced reasoning" },
        { "effort": "max", "description": "Deep reasoning" }
      ],
      "shell_type": "shell_command",
      "visibility": "list",
      "supported_in_api": true,
      "priority": 0,
      "base_instructions": "",
      "supports_reasoning_summaries": true,
      "default_reasoning_summary": "none",
      "support_verbosity": false,
      "apply_patch_tool_type": "freeform",
      "truncation_policy": { "mode": "bytes", "limit": 10000 },
      "context_window": 1048576,
      "max_context_window": 1048576,
      "effective_context_window_percent": 95,
      "supports_parallel_tool_calls": true,
      "experimental_supported_tools": [],
      "input_modalities": ["text"]
    }
  ]
}
EOF

if /usr/bin/security find-generic-password -a "$ACCOUNT" -s "$SERVICE" >/dev/null 2>&1; then
  echo "keychain: item '$SERVICE' for '$ACCOUNT' found"
else
  echo "keychain: item '$SERVICE' not found. Store your Z.ai key (you will be prompted):"
  echo "  security add-generic-password -a \"$ACCOUNT\" -s $SERVICE -U -w"
fi
