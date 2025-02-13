import logging
from .command import Command

LOGGER = logging.getLogger(__name__)

async def project_callback(ctx, *args):
    await ctx.send("project")


Project = Command("Project", "Manage your projects", project_callback)
