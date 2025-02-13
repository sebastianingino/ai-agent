from discord.ext import commands
from .project import Project

def register(bot: commands.Bot):
    bot.add_command(commands.command(name=Project.name.lower(), help=Project.help)(Project.entry))
