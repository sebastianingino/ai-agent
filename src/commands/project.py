import logging

import discord

from src.reactions import Reactions

from .command import command, CommandContext
from ..mistral.chat import Chat
from ..model.project import Project as ProjectModel
from ..model.user import User as UserModel

LOGGER = logging.getLogger(__name__)


@command("Project", "Manage your projects")
async def Project(ctx: CommandContext, *args: str):
    await ctx.send(await Chat.help(ctx.command_stack[-1].helptext() or ""))


@command("New", "Create a new project", parent=Project)
async def project_new(ctx: CommandContext, *args: str):
    if len(args) != 1:
        return await ctx.send("Usage: !project new [name]")
    name = args[0]

    existing_project = await ProjectModel.find(name=name).first_or_none()
    if not existing_project:
        project = ProjectModel(name=name, owner=ctx.user)
        await project.insert()
        Reactions.register_handler(ctx.message, "✅", set_default, project)
        await ctx.send(
            f"Project {name} created. React with ✅ to set the project as your default."
        )


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


async def project_invite(ctx: CommandContext, *args: str):
    pass


async def project_kick(ctx: CommandContext, *args: str):
    pass


async def project_leave(ctx: CommandContext, *args: str):
    pass


# Reaction Handlers
async def set_default(message: discord.Message, user: UserModel, project: ProjectModel):
    user.default_project = project.id
    await user.update()
    await project.update()
    await message.reply(f"Project {project.name} set as default.")
