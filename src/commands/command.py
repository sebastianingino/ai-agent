import logging
from typing import Any, List, Optional, Set, Tuple

from discord.ext import commands

LOGGER = logging.getLogger(__name__)

class Command:
    name: str
    help: Optional[str]
    callback: Any

    subcommands: List["Command"]
    names: Set[str]

    def __init__(self, name: str, help: Optional[str], callback, subcommands: Optional[List["Command"]] = None):
        self.name = name
        self.help = help
        self.callback = callback

        self.subcommands = subcommands or []
        self.names = set(subcommand.name for subcommand in self.subcommands)

        self.help = f"""
## {self.name}: {self.help}

**Usage:**
```
!{self.name.lower()} [subcommand] [args...]
```

**Subcommands:**
{"".join(f"!{subcommand.name} - {subcommand.help}\n" for subcommand in self.subcommands)}
        """.strip()

    async def entry(self, ctx: commands.Context, *args: str):
        action = self.parse(args)
        LOGGER.debug(f"Command {self.name} entry {args} -> {action}")
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

    async def _default_help(self, ctx: commands.Context, *args: str):
        await ctx.send(self.help)

