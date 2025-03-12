import functools
import logging
from typing import List

import discord

from actions.action import Action, apply_multiple
from actions.document import DocumentAdd, DocumentList, DocumentRemove, DocumentSearch
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

from arguments.parser import ArgParser
from commands.command import command, CommandContext
from mistral import parsers, rag
from mistral.chat import Chat
from model.project import Project as ProjectModel
from model.user import User as UserModel
from parsers import content as content_parser
from response.ButtonResponse import binary_response
from util import messages
from util.util import preflight_execute, result_collapse

LOGGER = logging.getLogger(__name__)


@command("Project", "Manage your projects")
async def project_entry(ctx: CommandContext, *args: str):
    if len(args) > 0:
        return await ctx.reply(
            "Sorry, no command exists with that name. Use `!project help` to see a list of available commands."
        )
    return await ctx.reply(await Chat.help(ctx.command_stack[-1].helptext() or ""))


@command("New", "Create a new project", parent=project_entry)
async def project_new(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!project new [name]`")
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
        return await ctx.reply("Usage: `!project list`")

    return await ctx.reply(await preflight_execute(ProjectList(), ctx))


@command("Info", "Get information about a project", parent=project_entry)
async def project_info(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!project info [name]`")
    name = " ".join(args)

    return await ctx.reply(await preflight_execute(ProjectInfo(name=name), ctx))


@command("Deadline", "Set a deadline for a project", parent=project_entry)
async def project_deadline(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!project deadline [when] -p [project]`")

    parser = ArgParser()
    parser.add_argument("project", "p")

    when = parser.parse(args)
    return await ctx.reply(
        await preflight_execute(ProjectDeadline(when=when, project=parser.project), ctx)
    )


@command("Delete", "Delete a project", parent=project_entry)
async def project_delete(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!project delete [name]`")
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
        return await ctx.reply("Usage: `!project invite [name] [users]`")

    name = " ".join(args for args in args if not args.startswith("<@"))

    if len(name.strip()) == 0:
        return await ctx.reply("Usage: `!project invite [name] [users]`")

    if len(ctx.message.mentions) < 1:
        return await ctx.reply("Usage: `!project invite [name] [users]`")

    users = [user.id for user in ctx.message.mentions]

    return await ctx.reply(
        await preflight_execute(ProjectInvite(name=name, users=users), ctx),
    )


@command("Kick", "Kick users from a project", parent=project_entry)
async def project_kick(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!project kick [name] [users]`")

    if len(ctx.message.mentions) < 1:
        return await ctx.reply("Usage: `!project kick [name] [users]`")

    name = " ".join(args for args in args if not args.startswith("<@"))
    if len(name.strip()) == 0:
        return await ctx.reply("Usage: `!project kick [name] [users]`")

    users = [user.id for user in ctx.message.mentions]

    return await ctx.reply(
        await preflight_execute(ProjectKick(name=name, users=users), ctx)
    )


@command("Leave", "Leave a project", parent=project_entry)
async def project_leave(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!project leave [name]`")
    name = " ".join(args)

    return await ctx.reply(await preflight_execute(ProjectLeave(name=name), ctx))


@command("Default", "Set a default project", parent=project_entry)
async def project_default(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!project default [name]`")
    name = " ".join(args)

    return await ctx.reply(await preflight_execute(ProjectSetDefault(name=name), ctx))


@command(
    "Import",
    "Import a project from text, images, documents, and links",
    parent=project_entry,
)
async def project_import(ctx: CommandContext, *args: str):
    async with ctx.typing():
        content_result = await content_parser.from_message(ctx.message, " ".join(args))
        if content_result.is_err():
            return await ctx.reply(
                f"Failed to parse content: {content_result.unwrap_err()}"
            )
        content = content_result.unwrap()
        async with ctx.message.channel.typing():
            tasks = parsers.import_project(content)
            if tasks.is_err():
                return await ctx.reply(
                    "Looks like there was an error importing the project. Please try again."
                )

            response = """
    Are you sure you want to import this project?
    This will create a new project with the following actions:
            """.strip()

            for action in tasks.unwrap():
                response += f"\n- {str(action)}{' ❗️' if action.unsafe else ''}"

            actions = tasks.unwrap()
            chunks = messages.chunkify(response)
            for chunk in chunks[:-1]:
                await ctx.reply(chunk)
            return await ctx.reply(
                chunks[-1],
                view=binary_response(
                    functools.partial(apply_actions, actions), user=ctx.author
                ),
            )


@command("doc", "Manage your project's documents", parent=project_entry)
async def project_document(ctx: CommandContext, *args: str):
    return await ctx.reply("Usage: `!project doc [add | remove | list | ask] ...`")


@command("add", "Add documents to the project", parent=project_document)
async def project_document_add(ctx: CommandContext, *args: str):
    if len(ctx.message.attachments) == 0 and len(args) == 0:
        return await ctx.reply(
            "Usage: `!project doc add [url] [name] (-p <project>)` (or attach files)"
        )

    parser = ArgParser()
    parser.add_argument("project", "p")
    contents = parser.parse(args).split()
    url = contents[0] if len(contents) > 0 else ""

    if len(contents) > 1 or len(url) == 0 and len(ctx.message.attachments) == 0:
        return await ctx.reply(
            "Usage: `!project doc add [url] (-p <project>)` (or attach files)"
        )

    urls = [url] if len(url) > 0 else []
    for attachment in ctx.message.attachments:
        urls.append(attachment.url)

    async with ctx.typing():
        return await ctx.reply(
            await preflight_execute(DocumentAdd(urls=urls, project=parser.project), ctx)
        )


@command("remove", "Remove a document from the project", parent=project_document)
async def project_document_remove(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!project doc remove [name] (-p <project>)`")

    parser = ArgParser()
    parser.add_argument("project", "p")
    name = parser.parse(args)

    return await ctx.reply(
        await preflight_execute(DocumentRemove(name=name, project=parser.project), ctx)
    )


@command("list", "List documents in the project", parent=project_document)
async def project_document_list(ctx: CommandContext, *args: str):
    if len(args) > 0:
        return await ctx.reply("Usage: `!project doc list (<project>)`")

    project = " ".join(args) if len(args) > 0 else None

    return await ctx.reply(await preflight_execute(DocumentList(project=project), ctx))


@command("ask", "Ask a question about the project documents", parent=project_document)
async def project_document_search(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply(
            "Usage: `!project doc search [query] (-p <project>) (-l <limit=5>)`"
        )

    parser = ArgParser()
    parser.add_argument("project", "p")
    parser.add_argument("limit", "l", default="5")
    query = parser.parse(args)
    try:
        limit = int(parser.limit) if parser.limit else None
    except ValueError:
        limit = 5

    async with ctx.typing():
        action = DocumentSearch(query=query, project=parser.project, limit=limit)
        preflight = await action.preflight(ctx)
        if preflight.is_err():
            return await ctx.reply(action.preflight_wrap(preflight).unwrap_err())
        result = await action.execute(ctx)
        if result.is_err():
            return await ctx.reply(action.execute_wrap(result).unwrap_err())
        if len(result.unwrap()) == 0:
            return await ctx.reply(f"No results found for query '{query}'")
        response = await rag.respond(query, result.unwrap())
        for chunk in messages.chunkify(response):
            await ctx.reply(chunk)


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


async def apply_actions(actions: List[Action], interaction: discord.Interaction):
    result = await apply_multiple(actions, interaction.user, interaction.client)
    if result.is_err():
        return await interaction.response.send_message(
            f"Error importing project: {result.unwrap_err()}", ephemeral=True
        )
    if result.is_ok():
        return await interaction.response.send_message(
            "Project imported successfully.", ephemeral=True
        )
