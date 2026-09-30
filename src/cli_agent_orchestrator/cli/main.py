"""Main CLI entry point for CLI Agent Orchestrator.

Keep this module cheap to import. Every ``cao`` invocation imports it, and so does every
shell-completion request, which zsh-autocomplete sends as you type. Subcommands are
registered in ``_COMMANDS`` below and their modules are imported only when that command is
used; see ``cli/lazy_group.py``. ``test/cli/test_cli_startup.py`` fails if importing this
module, ``cao --help`` or ``cao <Tab>`` pulls in a command module or a heavy dependency.
"""

from importlib.metadata import PackageNotFoundError, version

import click

from cli_agent_orchestrator.cli.lazy_group import LazyCommand, LazyGroup

try:
    __version__ = version("cli-agent-orchestrator")
except PackageNotFoundError:
    __version__ = "unknown"


def _lazy(module: str, attribute: str, help: str, hidden: bool = False) -> LazyCommand:
    return LazyCommand(f"cli_agent_orchestrator.cli.commands.{module}:{attribute}", help, hidden)


# Register commands: name -> (module in cli/commands/, command object, help line, hidden).
# The help line and hidden flag are what `cao --help` and shell completion show without
# importing the module, so they must match the command's docstring and decorator. The
# placeholder test in test/cli/test_cli_startup.py fails if they drift.
_COMMANDS = {
    "agent": _lazy("agent", "agent", "Orchestrate other agents from the shell."),
    "profile": _lazy("profile", "profile", "Manage agent profiles."),
    "launch": _lazy("launch", "launch", "Launch cao session with specified agent profile."),
    "config": _lazy(
        "config", "config", "Inspect and edit unified CAO configuration (settings.json)."
    ),
    "init": _lazy("init", "init", "Initialize CLI Agent Orchestrator database."),
    "install": _lazy(
        "install",
        "install",
        "Install an agent from local store, built-in store, URL, or file path.",
    ),
    "shutdown": _lazy(
        "shutdown", "shutdown", "Shutdown tmux sessions and cleanup terminal records."
    ),
    "schedule": _lazy("schedule", "schedule", "Manage scheduled agent flows."),
    # deprecated alias for 'schedule' (issue #378)
    "flow": _lazy("schedule", "flow", "[Deprecated] Alias for 'cao schedule'.", hidden=True),
    "env": _lazy("env", "env", "Manage CAO environment variables."),
    "mcp-server": _lazy("mcp_server", "mcp_server", "Start the CAO MCP server."),
    "info": _lazy("info", "info", "Display information about the current session."),
    "memory": _lazy("memory", "memory", "Manage CAO memories."),
    "skills": _lazy("skills", "skills", "Manage installed skills."),
    # Agent Plugins 1.0.0 (docs/agent-plugins.md). Distinct from the event-plugin
    # system in plugins/. The verb itself is maintainer decision M1 — see the
    # module docstring; changing it is a one-line edit here.
    "plugin": _lazy(
        "agent_plugin",
        "agent_plugin",
        "Manage agent plugins (Agent Plugins 1.0.0).",
        hidden=True,
    ),
    "session": _lazy("session", "session", "Manage CAO sessions."),
    "terminal": _lazy("terminal", "terminal", "Manage CAO terminals."),
    # Remote fleets. `cao fleet`/`cao worker` reach a cluster's worker broker over
    # HTTP; every other command here talks to the cao-server on this machine.
    "fleet": _lazy("fleet", "fleet", "Inspect and tear down a CAO fleet's workers."),
    "worker": _lazy("worker", "worker", "Inspect and talk to workers in a CAO cluster."),
    "workflow": _lazy("workflow", "workflow", "Author and inspect CAO workflow specs."),
    "update": _lazy("update", "update", "Update CAO to the latest version."),
    # bundled Rust terminal UI (issue #321)
    "tui": _lazy("tui", "tui", "Launch the terminal UI (bundled Rust binary)."),
}


@click.group(cls=LazyGroup, lazy_commands=_COMMANDS)
@click.version_option(__version__, "-V", "--version", prog_name="cao")
def cli():
    """CLI Agent Orchestrator."""


if __name__ == "__main__":
    cli()
