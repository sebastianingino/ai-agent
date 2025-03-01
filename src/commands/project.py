import logging
from typing import List

import discord

from actions.action import ActionContext
from actions.project import ProjectDelete, ProjectInfo, ProjectInvite, ProjectList, ProjectNew
from reactions import Reactions

from commands.command import command, CommandContext
from mistral.chat import Chat
from model.project import Project as ProjectModel
from model.user import User as UserModel
from util.util import result_collapse

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

    action = ProjectList()
    preflight = await action.preflight(ctx)
    if preflight.is_err():
        return await ctx.reply(action.preflight_wrap(preflight).unwrap_err())

    execute = await action.execute(ctx)
    return await ctx.reply(result_collapse(action.execute_wrap(execute)))


@command("Info", "Get information about a project", parent=project_entry)
async def project_info(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project info [name]")
    name = " ".join(args)

    action = ProjectInfo(name=name)
    preflight = await action.preflight(ctx)
    if preflight.is_err():
        return await ctx.reply(action.preflight_wrap(preflight).unwrap_err())

    execute = await action.execute(ctx)
    return await ctx.reply(result_collapse(action.execute_wrap(execute)))


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

    action = ProjectInvite(name=name, users=users)
    preflight = await action.preflight(ctx)
    if preflight.is_err():
        return await ctx.reply(action.preflight_wrap(preflight).unwrap_err())

    execute = await action.execute(ctx)
    return await ctx.reply(result_collapse(action.execute_wrap(execute)))


@command("Kick", "Kick users from a project", parent=project_entry)
async def project_kick(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project kick [name] [users]")

    name = " ".join(args for args in args if not args.startswith("<@"))

    mentioned = ctx.message.mentions
    if len(mentioned) < 1:
        return await ctx.reply("Usage: !project kick [name] [users]")

    project = await ProjectModel.find_one(
        ProjectModel.name == name, ProjectModel.owner == ctx.user.id
    )
    if not project:
        return await ctx.reply(f"Project {name} not found.")

    for user in mentioned:
        user_model = await UserModel.find_one(
            UserModel.discord_id == user.id, fetch_links=True
        )
        if not user_model:
            user_model = UserModel(discord_id=user.id)
            await user_model.insert()
        project.members.remove(user_model.id)
        user_model.projects.remove(project)
        await user_model.save()
    await project.save()

    return await ctx.reply(
        f"User{'s' if len(mentioned) > 1 else ''} {', '.join(user.mention for user in mentioned)} removed from project {name}."
    )


@command("Leave", "Leave a project", parent=project_entry)
async def project_leave(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project leave [name]")
    name = " ".join(args)

    for project in ctx.user.projects:
        if project.name == name:
            ctx.user.projects.remove(project)
            await ctx.user.save()
            return await ctx.reply(f"Left project {name}.")
    return await ctx.reply(f"Project {name} not found.")


# Reaction Handlers
async def set_default(message: discord.Message, user: UserModel, project: ProjectModel):
    user.default_project = project
    await user.save()
    await message.reply(f"Project {project.name} set as default.")


async def delete_project(message: discord.Message, _: UserModel, action: ProjectDelete):
    execute = await action.execute(None)  # type: ignore
    return await message.reply(result_collapse(action.execute_wrap(execute)))
