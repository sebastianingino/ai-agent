import asyncio
import os
import coloredlogs
import discord
import logging

from discord.ext import commands
from database.database import init_database
from model import Models
from reactions import Reactions
from dotenv import load_dotenv
from agent import MistralAgent
import commands as bot_commands
from util.messages import bot_included

PREFIX = "!"

# Setup logging
LOGGER = logging.getLogger("discoin")
coloredlogs.install(level="DEBUG", fmt="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.INFO)

# Load the environment variables
load_dotenv()

# Create the bot with all intents
# The message content and members intent must be enabled in the Discord Developer Portal for the bot to work.
intents = discord.Intents.all()

bot: commands.Bot
environment = os.getenv("ENVIRONMENT")
if environment == "DEV":
    from test.mockbot import MockBot
    bot = MockBot(command_prefix=PREFIX, intents=intents)  # type: ignore
else:
    bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Import the Mistral agent from the agent.py file
agent = MistralAgent()


# Get the token from the environment variables
token = os.getenv("DISCORD_TOKEN")

# Connect to MongoDB
asyncio.run(init_database(Models))


@bot.event
async def on_ready():
    """
    Called when the client is done preparing the data received from Discord.
    Prints message on terminal when bot successfully connects to discord.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_ready
    """
    LOGGER.info(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message: discord.Message):
    """
    Called when a message is sent in any channel the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message
    """
    LOGGER.info(f"Processing message from {message.author}: {message.content}")

    # Don't delete this line! It's necessary for the bot to process commands.
    await bot.process_commands(message)

    # Ignore messages from self or other bots to prevent infinite loops.
    if message.author.bot or message.content.startswith("!"):
        return
    
    # Ignore threads/messages that haven't included the bot in the past
    if not (await bot_included(message)):
        return
    
    # Get the context of the message
    context = await bot.get_context(message)

    # Process the message with the agent you wrote
    # Open up the agent.py file to customize the agent
    response = await agent.run(message)

    # Send the response back to the channel
    await message.reply(response)


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


# Commands
bot_commands.register(bot)


# Debugging command
@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.reply("Pong!")
    else:
        await ctx.reply(f"Pong! Your argument was {arg}")

async def main():
    # Connect to MongoDB
    await init_database(Models)

    # Start the bot, connecting it to the gateway
    await bot.start(token)  # type: ignore


if __name__ == "__main__":
    asyncio.run(main())
