import logging

import discord

from actions.project import (
    ProjectDelete,
    ProjectInfo,
    ProjectInvite,
    ProjectKick,
    ProjectLeave,
    ProjectList,
    ProjectNew,
)
from reactions import Reactions

from commands.command import command, CommandContext
from mistral.chat import Chat
from model.project import Project as ProjectModel
from model.user import User as UserModel
from util.util import preflight_execute, result_collapse

LOGGER = logging.getLogger(__name__)


@command("Project", "Manage your projects")
async def project_entry(ctx: CommandContext, *args: str):
    await ctx.reply(await Chat.help(ctx.command_stack[-1].helptext() or ""))


@command("New", "Create a new project", parent=project_entry)
async def project_new(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project new [name]")
    name = " ".join(args)

    action = ProjectNew(name=name)
    preflight = await action.preflight(ctx)
    if preflight.is_err():
        project = preflight.unwrap_err()
        if project.id == ctx.user.default_project.id:  # type: ignore
            return await ctx.reply(
                f"Project {name} already exists and is your default project."
            )

        Reactions.register_handler(ctx.message, "✅", set_default, project)
        return await ctx.reply(
            f"Project {name} already exists. React with ✅ to set the project as your default."
        )

    execute = await action.execute(ctx)
    if execute.is_err():
        return await ctx.reply(
            "Looks like something went wrong. Please try again later."
        )

    project = execute.unwrap()
    Reactions.register_handler(ctx.message, "✅", set_default, project)
    return await ctx.reply(
        f"Project {name} created. React with ✅ to set the project as your default."
    )


@command("List", "List your projects", parent=project_entry)
async def project_list(ctx: CommandContext, *args: str):
    if len(args) > 0:
        return await ctx.reply("Usage: !project list")

    return await ctx.reply(await preflight_execute(ProjectList(), ctx))


@command("Info", "Get information about a project", parent=project_entry)
async def project_info(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project info [name]")
    name = " ".join(args)

    return await ctx.reply(await preflight_execute(ProjectInfo(name=name), ctx))


async def project_deadline(ctx: CommandContext, *args: str):
    pass


@command("Delete", "Delete a project", parent=project_entry)
async def project_delete(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project delete [name]")
    name = " ".join(args)

    action = ProjectDelete(name=name)
    preflight = await action.preflight(ctx)
    if preflight.is_err():
        return await ctx.reply(action.preflight_wrap(preflight).unwrap_err())

    Reactions.register_handler(ctx.message, "✅", delete_project, action)
    return await ctx.reply(
        f"Are you sure you want to delete project {name}? React with ✅ to confirm."
    )


@command("Invite", "Invite users to a project", parent=project_entry)
async def project_invite(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project invite [name] [users]")

    name = " ".join(args for args in args if not args.startswith("<@"))
    users = [user.id for user in ctx.message.mentions]

    return await ctx.reply(
        await preflight_execute(ProjectInvite(name=name, users=users), ctx)
    )


@command("Kick", "Kick users from a project", parent=project_entry)
async def project_kick(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project kick [name] [users]")

    name = " ".join(args for args in args if not args.startswith("<@"))
    users = [user.id for user in ctx.message.mentions]

    return await ctx.reply(
        await preflight_execute(ProjectKick(name=name, users=users), ctx)
    )


@command("Leave", "Leave a project", parent=project_entry)
async def project_leave(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project leave [name]")
    name = " ".join(args)

    return await ctx.reply(await preflight_execute(ProjectLeave(name=name), ctx))


# Reaction Handlers
async def set_default(message: discord.Message, user: UserModel, project: ProjectModel):
    user.default_project = project
    await user.save()
    await message.reply(f"Project {project.name} set as default.")


async def delete_project(message: discord.Message, _: UserModel, action: ProjectDelete):
    execute = await action.execute(None)  # type: ignore
    return await message.reply(result_collapse(action.execute_wrap(execute)))
