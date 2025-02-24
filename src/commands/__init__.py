from discord.ext import commands
from .project import Project

def register(bot: commands.Bot):
    @bot.command(name=Project.name.lower(), help=Project.help)
    async def project_entry(ctx: commands.Context, *args: str):
        await Project.entry(ctx, *args)
