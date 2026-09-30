"""A Click group that imports a subcommand's module only when that subcommand is used.

WHY: ``cao --help`` and shell completion (``_CAO_COMPLETE=zsh_complete cao``) list every
top-level command with its one-line help. With eager registration, printing that list meant
importing every command module and, through them, fastmcp, SQLAlchemy, FastAPI and the
pydantic models: well over half a second before the first line of output, and about two with
cold bytecode. zsh-autocomplete runs completion as you type with a 1s budget, so after a
reboot or reinstall the live list for ``cao`` timed out.

WHY NOT A PLAIN LAZY GROUP: Click builds both the "Commands:" section and the completion
candidates from each subcommand's ``get_short_help_str()`` and ``hidden`` flag, so a group
that only defers ``get_command`` still imports every module the moment anything lists them.
Each entry here therefore also carries its help text and hidden flag. While Click is
*describing* the group (``format_commands`` and ``shell_complete``) it gets a placeholder
``click.Command`` built from those values, so Click's own formatting, truncation and
hidden-filtering produce the same output as before. Resolving a subcommand to run it, show its
own ``--help``, or complete below it always gets the real command.

The static text can drift from the real docstring. ``test/cli/test_cli_startup.py`` compares
every placeholder against the command it stands in for, so drift fails the build.
"""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator, Mapping, Optional

import click

if TYPE_CHECKING:
    from click.shell_completion import CompletionItem


@dataclass(frozen=True)
class LazyCommand:
    """Where a subcommand lives, plus what help and completion need to list it unloaded."""

    #: ``"package.module:attribute"`` of the ``click.Command`` object.
    import_path: str
    #: The first paragraph of the command's help. That paragraph is all Click's
    #: ``make_default_short_help`` reads, so the listed line matches the real command's.
    help: str
    hidden: bool = False

    def load(self) -> click.Command:
        """Import the command's module and return the command object."""
        module_name, _, attribute = self.import_path.partition(":")
        command = getattr(importlib.import_module(module_name), attribute)
        if not isinstance(command, click.Command):
            raise TypeError(f"{self.import_path} is {type(command).__name__}, not a click.Command")
        return command

    def placeholder(self, name: str) -> click.Command:
        """A stand-in with the same short help and hidden flag, for listing only."""
        return click.Command(name, help=self.help, hidden=self.hidden)


class LazyGroup(click.Group):
    """A ``click.Group`` whose ``lazy_commands`` are imported on first use.

    A lazy command is loaded when ``get_command`` resolves it, and it is then registered in
    ``self.commands`` like an eagerly added command. Eager ``add_command`` still works.
    """

    def __init__(
        self,
        *args: Any,
        lazy_commands: Optional[Mapping[str, LazyCommand]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.lazy_commands: dict[str, LazyCommand] = dict(lazy_commands or {})
        self._describing = False

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted({*self.commands, *self.lazy_commands})

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        command = self.commands.get(cmd_name)
        if command is not None:
            return command
        lazy = self.lazy_commands.get(cmd_name)
        if lazy is None:
            return None
        if self._describing:
            return lazy.placeholder(cmd_name)
        command = lazy.load()
        self.add_command(command, cmd_name)
        return command

    @contextmanager
    def _describe_only(self) -> Iterator[None]:
        """Within this block, ``get_command`` hands out placeholders for unloaded commands."""
        self._describing = True
        try:
            yield
        finally:
            self._describing = False

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        with self._describe_only():
            super().format_commands(ctx, formatter)

    def shell_complete(self, ctx: click.Context, incomplete: str) -> list[CompletionItem]:
        with self._describe_only():
            return super().shell_complete(ctx, incomplete)
