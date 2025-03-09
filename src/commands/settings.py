from actions.settings import SettingsDefaultProject
from commands.command import CommandContext, command
from mistral.chat import Chat
from util.util import preflight_execute


@command("Settings", "User settings")
async def settings_entry(ctx: CommandContext, *args: str):
    if len(args) > 0:
        return await ctx.reply("Sorry, I don't understand that command. Use `!settings help` to see a list of available commands.")
    return await ctx.reply(await Chat.help(ctx.command_stack[-1].helptext() or ""))


@command("Default", "Set your default project", parent=settings_entry)
async def settings_default(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: !settings default [project]")
    name = " ".join(args)

    await ctx.reply(await preflight_execute(SettingsDefaultProject(name=name), ctx))
