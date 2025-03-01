import logging
from typing import Any, List, Optional, Set, Tuple

from discord.ext import commands

from src.model.user import User as UserModel

LOGGER = logging.getLogger(__name__)


class CommandContext(commands.Context):
    command_stack: List["Command"]
    user: UserModel


def command(
    name: str,
    help: Optional[str],
    *,
    subcommands: Optional[List["Command"]] = None,
    parent: Optional["Command"] = None,
):
    def decorator(callback):
        result = Command(name, help, callback, subcommands)
        if parent:
            parent.add_subcommand(result)
        return result

    return decorator


class Command:
    name: str
    help: Optional[str]
    callback: Any

    subcommands: List["Command"]
    names: Set[str]

    def __init__(
        self,
        name: str,
        help: Optional[str],
        callback,
        subcommands: Optional[List["Command"]] = None,
    ):
        self.name = name
        self.help = help
        self.callback = callback

        self.subcommands = subcommands or []
        self.names = set(subcommand.name for subcommand in self.subcommands)

    async def entry(self, ctx: commands.Context, *args: str):
        action = self.parse(args)
        LOGGER.debug(f"Command {self.name} entry {args} -> {action}")
        if "command_stack" not in ctx.__dict__:
            ctx.command_stack = []  # type: ignore
        if "user" not in ctx.__dict__:
            ctx.user = await UserModel.find_one(discord_id=ctx.author.id)  # type: ignore
        ctx.command_stack.append(self)  # type: ignore
        if action is None:
            return await self.callback(ctx, *args)
        return await action.entry(ctx, *args[1:])

    def parse(self, args: Tuple[str, ...]) -> Optional["Command"]:
        LOGGER.debug(f"Command {self.name} parsing {args}")
        if len(args) == 0:
            return None
        if len(args) == 1 and args[0] == "help" and "help" not in self.names:
            return Command("help", None, self._default_help)

        for subcommand in self.subcommands:
            if subcommand.name == args[0]:
                return subcommand
        return None

    def add_subcommand(self, subcommand: "Command"):
        self.subcommands.append(subcommand)
        self.names.add(subcommand.name)

    def helptext(self):
        return f"""
## {self.name}: {self.help}

**Usage:**
```
!{self.name.lower()} [subcommand] [args...]
```
**Subcommands:**
{"".join(f"{subcommand.name.lower()} - {subcommand.help}\n" for subcommand in self.subcommands)}
        """.strip()

    async def _default_help(self, ctx: commands.Context, *args: str):
        await ctx.send(self.helptext())
