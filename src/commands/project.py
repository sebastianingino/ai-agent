import logging
from .command import command, CommandContext
from ..mistral.chat import Chat

LOGGER = logging.getLogger(__name__)

@command("Project", "Manage your projects")
async def Project(ctx: CommandContext, *args: str):
    await ctx.send(await Chat.help(ctx.command_stack[-1].helptext() or ""))

@command("New", "Create a new project", parent=Project)
async def project_new(ctx: CommandContext, *args: str):
    if len(args) != 1:
        return await ctx.send("Usage: !project new [name]")
    pass

async def project_list(ctx: CommandContext, *args: str):
    pass

async def project_status(ctx: CommandContext, *args: str):
    pass

async def project_delete(ctx: CommandContext, *args: str):
    pass

async def project_edit(ctx: CommandContext, *args: str):
    pass

async def project_add(ctx: CommandContext, *args: str):
    pass

async def project_remove(ctx: CommandContext, *args: str):
    pass
