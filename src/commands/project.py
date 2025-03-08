import functools
import logging

import discord

from actions.project import (
    ProjectDeadline,
    ProjectDelete,
    ProjectInfo,
    ProjectInvite,
    ProjectKick,
    ProjectLeave,
    ProjectList,
    ProjectNew,
    ProjectSetDefault,
)

from commands.command import command, CommandContext
from mistral import functions
from mistral.chat import Chat
from model.project import Project as ProjectModel
from model.user import User as UserModel
from parsers import content as content_parser
from response.ButtonResponse import binary_response
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

        return await ctx.reply(
            f"Project {name} already exists. Do you want to set it as your default project?",
            view=binary_response(
                functools.partial(set_default, project, ctx.user), user=ctx.author
            ),
        )

    execute = await action.execute(ctx)
    if execute.is_err():
        return await ctx.reply(
            "Looks like something went wrong. Please try again later."
        )

    project = execute.unwrap()
    return await ctx.reply(
        f"Project {name} created. Do you want to set it as your default project?",
        view=binary_response(
            functools.partial(set_default, project, ctx.user), user=ctx.author
        ),
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


@command("Deadline", "Set a deadline for a project", parent=project_entry)
async def project_deadline(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project deadline [when] -n [name]")
    when = " ".join(args)

    return await ctx.reply(await preflight_execute(ProjectDeadline(when=when), ctx))


@command("Delete", "Delete a project", parent=project_entry)
async def project_delete(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project delete [name]")
    name = " ".join(args)

    action = ProjectDelete(name=name)
    preflight = await action.preflight(ctx)
    if preflight.is_err():
        return await ctx.reply(action.preflight_wrap(preflight).unwrap_err())

    return await ctx.reply(
        f"Are you sure you want to delete project {name}?",
        view=binary_response(
            functools.partial(delete_project, action), user=ctx.author
        ),
    )


@command("Invite", "Invite users to a project", parent=project_entry)
async def project_invite(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project invite [name] [users]")

    name = " ".join(args for args in args if not args.startswith("<@"))

    if len(name.strip()) == 0:
        return await ctx.reply("Usage: !project invite [name] [users]")

    if len(ctx.message.mentions) < 1:
        return await ctx.reply("Usage: !project invite [name] [users]")

    users = [user.id for user in ctx.message.mentions]

    return await ctx.reply(
        await preflight_execute(ProjectInvite(name=name, users=users), ctx),
    )


@command("Kick", "Kick users from a project", parent=project_entry)
async def project_kick(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project kick [name] [users]")
    
    if len(ctx.message.mentions) < 1:
        return await ctx.reply("Usage: !project kick [name] [users]")

    name = " ".join(args for args in args if not args.startswith("<@"))
    if len(name.strip()) == 0:
        return await ctx.reply("Usage: !project kick [name] [users]")

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


@command("Default", "Set a default project", parent=project_entry)
async def project_default(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project default [name]")
    name = " ".join(args)

    return await ctx.reply(await preflight_execute(ProjectSetDefault(name=name), ctx))


@command("Import", "Import a project from another service", parent=project_entry)
async def project_import(ctx: CommandContext, *args: str):
    content_result = await content_parser.from_message(ctx.message, " ".join(args))
    if content_result.is_err():
        return await ctx.reply(
            f"Failed to parse content: {content_result.unwrap_err()}"
        )
    content = content_result.unwrap()
    tasks = functions.import_project(content)
    print(tasks)
    return await ctx.reply("Imported project")

# Response Handlers
async def set_default(
    project: ProjectModel, user: UserModel, interaction: discord.Interaction
):
    user.default_project = project  # type: ignore
    await user.save()
    await interaction.response.send_message(
        f"Project {project.name} set as default.", ephemeral=True
    )


async def delete_project(action: ProjectDelete, interaction: discord.Interaction):
    result = await action.execute(None)  # type: ignore
    return await interaction.response.send_message(
        result_collapse(action.execute_wrap(result)), ephemeral=True
    )
