import asyncio
import os
import coloredlogs  # type: ignore
import discord
import logging
from collections import defaultdict
from typing import DefaultDict, List
from beanie import PydanticObjectId
from discord.ext import commands
from database.database import init_database
from model import Models
from model.task import Task
from model.user import User
from reactions import Reactions
from dotenv import load_dotenv
from mistral.agent import Agent
from commands.register import register
from util import messages
from discord.ext import tasks
from datetime import datetime, time, timedelta

# Sentry for error tracking
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

environment = os.getenv("ENV")

sentry_sdk.init(
    dsn="https://eb37c6a6f385fc23e9b3f55308e4af7e@o4507331026747392.ingest.us.sentry.io/4508957002956800",
    send_default_pii=True,
    integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
    environment=environment or "local",
)

# Google Cloud Logging
if environment == "production":
    import google.cloud.logging as cloud_logging

    client = cloud_logging.Client()
    client.setup_logging()
else:
    coloredlogs.install(
        level="DEBUG", fmt="%(asctime)s %(name)s %(levelname)s %(message)s"
    )

PREFIX = "!"

# Setup logging
LOGGER = logging.getLogger("discoin")
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.INFO)
LOGGER.info("Environment: %s", environment)

# Load the environment variables
load_dotenv()

# Create the bot with all intents
# The message content and members intent must be enabled in the Discord Developer Portal for the bot to work.
intents = discord.Intents.all()


class Bot(commands.Bot):
    async def on_command_error(
        self, context: commands.Context, exception: commands.CommandError
    ) -> None:
        if isinstance(exception, commands.CommandNotFound):
            await context.reply(
                "Sorry, I don't recognize that command. Try `!help` for a list of commands."
            )
        else:
            sentry_sdk.capture_exception(exception)
            await context.send(
                "Sorry, an error occurred while processing your command."
            )


bot: Bot
if environment == "development":
    from test.mockbot import MockBot

    bot = MockBot(command_prefix=PREFIX, intents=intents)  # type: ignore
else:
    bot = Bot(command_prefix=PREFIX, intents=intents)


@bot.event
async def on_ready():
    """
    Called when the client is done preparing the data received from Discord.
    Prints message on terminal when bot successfully connects to discord.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_ready
    """
    LOGGER.info(f"{bot.user} has connected to Discord!")
    if not check_due_tasks.is_running():
        check_due_tasks.start()
    if not daily_task_report.is_running():
        daily_task_report.start()


@bot.event
async def on_message(message: discord.Message):
    """
    Called when a message is sent in any channel the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message
    """
    # Ignore messages to the Admin Bot
    if message.content.startswith("."):
        return

    if not message.author.bot or message.content.startswith("!"):
        LOGGER.info(f"Processing message from {message.author}: {message.content}")

    # Don't delete this line! It's necessary for the bot to process commands.
    await bot.process_commands(message)

    # Ignore messages from self or other bots to prevent infinite loops.
    if message.author.bot or message.content.startswith("!"):
        return

    # Get the context of the message
    context = await messages.context(message)
    # Ignore threads/messages that haven't included the bot in the past 200 messages
    if not await messages.bot_included(context) and not messages.is_bot_dm(message):
        return

    async with message.channel.typing():
        # Process the message with the agent you wrote
        # Open up the agent.py file to customize the agent
        response = await Agent.handle(message, context, bot)
        if not response:
            return

        # Send the response back to the channel
        for chunk in messages.chunkify(response):
            message = await message.reply(chunk)


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """
    Called when a reaction is added to a message the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html
    """

    LOGGER.info(f"Reaction added by {user}: {reaction.emoji}")

    # Check if the message was awaiting a reaction
    message = reaction.message
    await Reactions.handle(reaction, message, user)


@tasks.loop(time=time(hour=8))
async def check_due_tasks() -> None:
    # Get today's date
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    try:
        # Find all tasks due today
        due_tasks = await Task.find(
            {"deadline": {"$gte": today, "$lt": tomorrow}, "completed": False}
        ).to_list()

        for task in due_tasks:
            # Get the task owner
            user = await User.get(task.owner)
            if not user:
                LOGGER.warning(f"User not found for task {task.id}")
                continue

            # Get the Discord user
            discord_user = bot.get_user(user.discord_id)
            if not discord_user:
                LOGGER.warning(f"Discord user not found for user ID {user.discord_id}")
                continue

            if not task.deadline:
                continue

            # Send reminder as DM
            try:
                channel = await discord_user.create_dm()
                await channel.send(
                    f"⏰ Task due today: **{task.name}**\nDeadline: {task.deadline.strftime('%Y-%m-%d %H:%M')}"
                )
            except Exception as e:
                LOGGER.error(f"Failed to send reminder for task {task.id}: {e}")
    except Exception as e:
        LOGGER.error(f"Error in check_due_tasks: {e}")


@tasks.loop(time=time(hour=17))
async def daily_task_report() -> None:
    channel = bot.get_channel(1337208671339282433)
    if not (
        isinstance(channel, discord.TextChannel)
        or isinstance(channel, discord.DMChannel)
    ):
        LOGGER.error("Channel not found.")
        return

    task_counts: DefaultDict[PydanticObjectId, int] = defaultdict(int)
    all_tasks = await Task.find({"completed": True}).to_list()
    now = datetime.now()

    for task in all_tasks:
        if task.completed_date and task.completed_date.date() == now.date():
            task_counts[task.owner] += 1

    if not task_counts:
        await channel.send("No tasks completed today. We'll get 'em tomorrow!")
        return

    max_completed = max(task_counts.values())
    top_users = [user for user, count in task_counts.items() if count == max_completed]

    top_usernames: List[discord.User] = []
    for person in top_users:
        user = await User.find_one({"_id": person}, fetch_links=True)
        if user:
            discord_user = await bot.fetch_user(user.discord_id)
            top_usernames.append(discord_user)
        else:
            LOGGER.error("No user found with this ID.")

    if len(top_users) == 1:
        winner = top_usernames[0]
        await channel.send(
            f"Congrats {winner.mention}! You completed the most tasks today with {max_completed} tasks. Thanks for your hard work! 🎉",
        )
    else:
        user_list = f"{', '.join([user.mention for user in top_usernames[:-1]])}, and {top_usernames[-1].mention}"
        await channel.send(
            f"Productive day! {user_list} all completed {max_completed} tasks each! Keep it up! 💪"
        )


# Register commands
register(bot)


# Debugging command
@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.reply("Pong!")
    else:
        await ctx.reply(f"Pong! Your argument was {arg}")


# User task commands
@bot.command(name="duetoday", help="Shows tasks due today.")
async def duetoday(ctx):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    try:
        # Find the user by their discord_id
        user = await User.find_one({"discord_id": ctx.author.id}, fetch_links=True)
        if not user:
            await ctx.reply("You need to be registered first.")
            return

        # Find due tasks for this user
        due_tasks = await Task.find(
            {
                "owner": user.id,
                "deadline": {"$gte": today, "$lt": tomorrow},
                "completed": False,
            }
        ).to_list()

        if not due_tasks:
            await ctx.reply("You have no tasks due today.")
            return

        response = "Tasks due today:\n"
        for task in due_tasks:
            if not task.deadline:
                continue
            time_str = task.deadline.strftime("%H:%M")
            response += f"• {task.name} - Due at {time_str}\n"

        await ctx.reply(response)
    except Exception as e:
        LOGGER.error(f"Error in duetoday command: {e}")
        await ctx.reply("An error occurred while retrieving your tasks.")


async def main():
    # Connect to MongoDB
    await init_database(Models)

    # Get the token from the environment variables
    token = os.getenv("DISCORD_TOKEN")
    # Start the bot, connecting it to the gateway
    await bot.start(token)  # type: ignore


if __name__ == "__main__":
    asyncio.run(main())
