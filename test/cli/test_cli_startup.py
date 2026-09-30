"""``cao --help`` and ``cao <Tab>`` must stay cheap to start.

Every shell-completion request runs ``cao`` from scratch, and zsh-autocomplete sends one as
you type with a 1s budget. When ``cli/main.py`` registered every command eagerly, that meant
importing fastmcp, SQLAlchemy, FastAPI and the pydantic models on each request, about 0.6s
warm and ~1.9s with cold bytecode, so after a reboot or reinstall the live completion list
for ``cao`` timed out.

The root group now loads each command module on first use (``cli/lazy_group.py``). These
tests pin that down by checking what a fresh interpreter has imported, not by timing it: an
import is deterministic, a wall-clock budget flakes on a loaded CI runner. They also check
the static help lines that stand in for unloaded commands against the real commands.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cli_agent_orchestrator.cli.main import cli

COMMAND_MODULE_PREFIX = "cli_agent_orchestrator.cli.commands."

# Each of these costs tens to hundreds of milliseconds to import, and none of them is
# needed to list commands.
HEAVY_DEPENDENCIES = (
    "apscheduler",
    "fastapi",
    "fastmcp",
    "jwt",
    "mcp",
    "pydantic",
    "requests",
    "sqlalchemy",
    "starlette",
    "uvicorn",
)

# Runs in a fresh interpreter: optionally drives the CLI the way the `cao` console script
# does, then records every module the process imported.
_PROBE = """
import json
import sys

from cli_agent_orchestrator.cli.main import cli

out_path, mode, *args = sys.argv[1:]
if mode == "run":
    try:
        cli.main(args=args, prog_name="cao")
    except SystemExit:
        pass
with open(out_path, "w") as out:
    json.dump(sorted(sys.modules), out)
"""


def _probe(
    tmp_path: Path, *args: str, mode: str = "run", env: dict[str, str] | None = None
) -> tuple[subprocess.CompletedProcess[str], set[str]]:
    modules_file = tmp_path / "modules.json"
    child_env = {k: v for k, v in os.environ.items() if not k.startswith(("_CAO_", "COMP_"))}
    child_env.update(env or {})
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, str(modules_file), mode, *args],
        capture_output=True,
        text=True,
        env=child_env,
        timeout=120,
    )
    assert modules_file.exists(), f"probe crashed:\n{result.stderr}"
    return result, set(json.loads(modules_file.read_text()))


def _command_modules(modules: set[str]) -> set[str]:
    return {m for m in modules if m.startswith(COMMAND_MODULE_PREFIX)}


def _heavy(modules: set[str]) -> set[str]:
    return {m for m in modules if m.split(".")[0] in HEAVY_DEPENDENCIES}


def test_importing_the_cli_loads_no_command_module_or_heavy_dependency(tmp_path):
    _, modules = _probe(tmp_path, mode="import")

    assert not _command_modules(modules)
    assert not _heavy(modules)


@pytest.mark.parametrize(
    ("args", "env", "expected"),
    [
        pytest.param(["--help"], {}, "Orchestrate other agents from the shell.", id="--help"),
        pytest.param([], {}, "Orchestrate other agents from the shell.", id="no-args"),
        pytest.param(["--version"], {}, "cao, version", id="--version"),
        pytest.param(
            [],
            {"_CAO_COMPLETE": "zsh_complete", "COMP_WORDS": "cao ", "COMP_CWORD": "1"},
            "agent\nOrchestrate other agents from the shell.",
            id="zsh-complete-root",
        ),
        pytest.param(
            [],
            {"_CAO_COMPLETE": "bash_complete", "COMP_WORDS": "cao s", "COMP_CWORD": "1"},
            "plain,schedule",
            id="bash-complete-prefix",
        ),
    ],
)
def test_listing_commands_imports_none_of_them(tmp_path, args, env, expected):
    """Help and root completion describe every command from static text alone.

    ``expected`` keeps this from passing on an empty listing: a group that lists nothing
    imports nothing too. Bare ``cao`` prints its help to stderr, hence both streams.
    """
    result, modules = _probe(tmp_path, *args, env=env)

    assert expected in result.stdout + result.stderr, result.stdout + result.stderr
    assert not _command_modules(modules)
    assert not _heavy(modules)


@pytest.mark.parametrize(
    ("command", "module"),
    [("update", "update"), ("mcp-server", "mcp_server")],
)
def test_a_command_loads_only_its_own_module(tmp_path, command, module):
    """``cao mcp-server --help`` also covers the deferred fastmcp import in that command."""
    result, modules = _probe(tmp_path, command, "--help")

    assert result.stdout.startswith(f"Usage: cao {command}"), result.stdout + result.stderr
    assert _command_modules(modules) == {COMMAND_MODULE_PREFIX + module}
    assert not _heavy(modules)


@pytest.mark.parametrize("name", sorted(cli.lazy_commands))
def test_the_static_listing_matches_the_real_command(name):
    """The help line and hidden flag in ``cli/main.py`` must match the command itself.

    They are what ``cao --help`` and shell completion show without importing the command,
    so a docstring edit that is not mirrored there would otherwise ship a stale listing.
    Short help is compared at every width Click might truncate to.
    """
    lazy = cli.lazy_commands[name]
    real = lazy.load()
    placeholder = lazy.placeholder(name)
    first_paragraph = " ".join((real.help or "").split("\n\n")[0].split())

    assert real.name == name, f"{lazy.import_path} is named {real.name!r}, registered as {name!r}"
    assert (
        placeholder.hidden == real.hidden
    ), f"{name!r}: hidden={real.hidden} on the command but {lazy.hidden} in cli/main.py"
    assert [placeholder.get_short_help_str(limit) for limit in range(1, 121)] == [
        real.get_short_help_str(limit) for limit in range(1, 121)
    ], f"{name!r}: set its help line in cli/main.py to {first_paragraph!r}"
