from typing import List, Union
import discord
from mistralai import AssistantMessage, SystemMessage, ToolMessage, UserMessage

CONTEXT_LIMIT = 200
RESET_POINT = "Bot state reset."

Prompt = List[Union[SystemMessage, ToolMessage, UserMessage, AssistantMessage]]


async def context(message: discord.Message):
    """
    Get the message context of the current message.
    """
    stack: List[discord.Message]
    if isinstance(message.channel, discord.Thread) or isinstance(
        message.channel, discord.DMChannel
    ):
        stack = []
        async for msg in message.channel.history(limit=CONTEXT_LIMIT):
            if msg.author.bot and msg.content == RESET_POINT:
                break
            stack.append(msg)
    else:
        stack = [message]
        while (
            stack[-1].reference
            and (resolved := stack[-1].reference.resolved)
            and isinstance(resolved, discord.Message)
            and len(stack) < CONTEXT_LIMIT
            and not (resolved.author.bot and resolved.content == RESET_POINT)
        ):
            stack.append(resolved)

    return stack[::-1]


async def context_to_prompt(context: List[discord.Message]) -> Prompt:
    """
    Convert a message context to a prompt.
    """
    prompt: Prompt = []
    for message in context:
        if message.author.bot:
            prompt.append(AssistantMessage(content=message.content))
        else:
            prompt.append(UserMessage(content=message.content))
    return prompt


async def bot_included(context: List[discord.Message]) -> bool:
    """
    Check if the bot is included in the message context.
    """
    for message in context:
        if message.author.bot:
            return True
    return False


async def is_bot_dm(message: discord.Message) -> bool:
    """
    Check if the message is a DM to the bot.
    """
    return isinstance(message.channel, discord.DMChannel)


def chunkify(content: str, max_length: int = 2000) -> List[str]:
    """
    Split content into chunks of at most `max_length` characters.
    """
    chunks = []
    while content:
        if len(content) <= max_length:
            chunks.append(content)
            break
        chunk = content[:max_length]
        if (pos := chunk.rfind("\n")) != -1:
            chunk = chunk[:pos]
        elif (pos := chunk.rfind(" ")) != -1:
            chunk = chunk[:pos]
        chunks.append(chunk)
        content = content[len(chunk) :]

    return chunks
