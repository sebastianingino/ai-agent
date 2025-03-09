from commands.command import command, CommandContext
from mistral.chat import Chat

@command("Task", "Manage your tasks")
async def task_entry(ctx: CommandContext, *args: str):
    if len(args) > 0:
        return await ctx.reply("Sorry, I don't understand that command. Use `!task help` to see a list of available commands.")
    return await ctx.reply(await Chat.help(ctx.command_stack[-1].helptext() or ""))
