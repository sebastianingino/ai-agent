from discord.ext import commands
from commands.project import project_entry as Project
from commands.settings import settings_entry as Settings

command_map = {
    "project": Project,
    "settings": Settings,
}


class Help(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        await self.context.reply(
            f"""
Welcome to the project manager bot! I can help you manage your projects and settings.
Use the `help` command to get help with a specific command (e.g. `!help project`).

**Available commands:**
{'\n'.join(f"- `{command.name.lower()}`: {command.help}" for command in command_map.values())}
            """.strip()
        )

    async def send_command_help(self, command):
        await self.context.reply(command_map[command.name.lower()].helptext())


def register(bot: commands.Bot):
    bot.help_command = Help()

    @bot.command(name=Project.name.lower(), help=Project.help)
    async def project_entry(ctx: commands.Context, *args: str):
        await Project.entry(ctx, *args)

    @bot.command(name=Settings.name.lower(), help=Settings.help)
    async def settings_entry(ctx: commands.Context, *args: str):
        await Settings.entry(ctx, *args)

    @bot.command(name="reset", help="Resets the bot's state.")
    async def reset(ctx: commands.Context):
        await ctx.reply("Bot state reset.")
