from discord.ext import commands
from commands.project import project_entry as Project

def register(bot: commands.Bot):
    @bot.command(name=Project.name.lower(), help=Project.help)
    async def project_entry(ctx: commands.Context, *args: str):
        await Project.entry(ctx, *args)
