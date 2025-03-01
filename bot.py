import asyncio
import os
import discord
import logging

from discord.ext import commands
from src.database.database import init_database
from src.model import Models
from src.reactions import Reactions
from test.mockbot import MockBot
from dotenv import load_dotenv
from agent import MistralAgent
import src.commands as bot_commands

PREFIX = "!"

# Setup logging
logger = logging.getLogger("discord")

# Load the environment variables
load_dotenv()

# Create the bot with all intents
# The message content and members intent must be enabled in the Discord Developer Portal for the bot to work.
intents = discord.Intents.all()

bot: commands.Bot
environment = os.getenv("ENVIRONMENT")
if environment == "DEV":
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
    logger.info(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message: discord.Message):
    """
    Called when a message is sent in any channel the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message
    """
    # Don't delete this line! It's necessary for the bot to process commands.
    await bot.process_commands(message)

    # Ignore messages from self or other bots to prevent infinite loops.
    if message.author.bot or message.content.startswith("!"):
        return

    # Process the message with the agent you wrote
    # Open up the agent.py file to customize the agent
    logger.info(f"Processing message from {message.author}: {message.content}")
    response = await agent.run(message)

    # Send the response back to the channel
    await message.reply(response)


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """
    Called when a reaction is added to a message the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html
    """

    # Check if the message was awaiting a reaction
    message = reaction.message
    if message.author == bot.user and Reactions.has_handler(message):
        Reactions.handle(reaction, reaction.message, user)
    elif Reactions.has_handler(message):
        # Check if the expected user reacted
        if user == message.author:
            Reactions.handle(reaction, reaction.message, user)
    elif (
        message.type == discord.MessageType.reply
        and message.reference
        and message.reference.resolved
        and isinstance(message.reference.resolved, discord.Message)
        and Reactions.has_handler(message.reference.resolved)
    ):
        # Check if previous message had a reaction handler
        Reactions.handle(reaction, message.reference.resolved, user)


# Commands
bot_commands.register(bot)


# This example command is here to show you how to add commands to the bot.
# Run !ping with any number of arguments to see the command in action.
# Feel free to delete this if your project will not need commands.
@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.send("Pong!")
    else:
        await ctx.send(f"Pong! Your argument was {arg}")


# Start the bot, connecting it to the gateway
bot.run(token)  # type: ignore
