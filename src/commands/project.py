import logging
from typing import List

import discord

from reactions import Reactions

from commands.command import command, CommandContext
from mistral.chat import Chat
from model.project import Project as ProjectModel
from model.user import User as UserModel

LOGGER = logging.getLogger(__name__)


@command("Project", "Manage your projects")
async def Project(ctx: CommandContext, *args: str):
    await ctx.reply(await Chat.help(ctx.command_stack[-1].helptext() or ""))


@command("New", "Create a new project", parent=Project)
async def project_new(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project new [name]")
    name = " ".join(args)

    existing_project = await ProjectModel.find_one(
        ProjectModel.name == name, ProjectModel.owner == ctx.user.id
    )
    if not existing_project:
        project = ProjectModel(name=name, owner=ctx.user.id)
        await project.insert()
        ctx.user.projects.append(project)
        await ctx.user.save()

        Reactions.register_handler(ctx.message, "✅", set_default, project)
        return await ctx.reply(
            f"Project {name} created. React with ✅ to set the project as your default."
        )

    if ctx.user.default_project == existing_project.id:
        return await ctx.reply(
            f"Project {name} already exists and is your default project."
        )

    Reactions.register_handler(ctx.message, "✅", set_default, existing_project)
    return await ctx.reply(
        f"Project {name} already exists. React with ✅ to set the project as your default."
    )


@command("List", "List your projects", parent=Project)
async def project_list(ctx: CommandContext, *args: str):
    if len(args) > 0:
        return await ctx.reply("Usage: !project list")
    if len(ctx.user.projects) == 0:
        return await ctx.reply("No projects found.")
    return await ctx.reply(
        "**Projects:**\n"
        + "\n".join(
            f"{"⭐ " if project == ctx.user.default_project else ""}{project.name}"
            for project in ctx.user.projects
        )
    )


@command("Info", "Get information about a project", parent=Project)
async def project_info(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project info [name]")
    name = " ".join(args)

    for project in ctx.user.projects:
        if project.name == name:
            owner = await UserModel.find_one(UserModel.id == project.owner)
            if not owner:
                return await ctx.reply(f"Project {name} not found.")

            members: List[discord.User] = []
            for member in project.members:
                user = await UserModel.find_one(UserModel.id == member)
                if user:
                    members.append(ctx.bot.get_user(user.discord_id))
            return await ctx.reply(
                f"**{project.name}**\n"
                f"Owner: {ctx.bot.get_user(owner.discord_id).mention}\n"
                f"Members: {', '.join(member.mention for member in members)}",
                allowed_mentions=discord.AllowedMentions.all(),
            )
    return await ctx.reply(f"Project {name} not found.")


async def project_deadline(ctx: CommandContext, *args: str):
    pass


@command("Delete", "Delete a project", parent=Project)
async def project_delete(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project delete [name]")
    name = " ".join(args)

    project = await ProjectModel.find_one(
        ProjectModel.name == name, ProjectModel.owner == ctx.user.id
    )
    if not project:
        return await ctx.reply(f"Project {name} not found.")

    Reactions.register_handler(ctx.message, "✅", delete_project, project)
    return await ctx.reply(
        f"Are you sure you want to delete project {name}? React with ✅ to confirm."
    )


@command("Invite", "Invite users to a project", parent=Project)
async def project_invite(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !project invite [name] [users]")

    name = " ".join(args for args in args if not args.startswith("<@"))

    mentioned = ctx.message.mentions
    if len(mentioned) < 1:
        return await ctx.reply("Usage: !project invite [name] [users]")

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
        project.members.append(user_model.id)
        user_model.projects.append(project)
        await user_model.save()
    await project.save()

    return await ctx.reply(
        f"User{'s' if len(mentioned) > 1 else ''} {', '.join(user.mention for user in mentioned)} added to project {name}."
    )


@command("Kick", "Kick users from a project", parent=Project)
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

@command("Leave", "Leave a project", parent=Project)
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


async def delete_project(message: discord.Message, _: UserModel, project: ProjectModel):
    await project.delete()
    await message.reply(f"Project {project.name} deleted.")
