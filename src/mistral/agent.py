import os
from typing import List
from mistralai import Mistral, SystemMessage, UserMessage
import discord

from util.messages import context_to_prompt

MISTRAL_MODEL = "mistral-small-latest"
SYSTEM_PROMPT = "You are a helpful and friendly project manager assistant."
ERROR_RESPONSE = "Looks like something went wrong. Please try again later."

class AgentModel:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

        self.client = Mistral(api_key=MISTRAL_API_KEY)

    async def run(self, message: discord.Message):
        # The simplest form of an agent
        # Send the message's content to Mistral's API and return Mistral's response

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message.content},
        ]

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )

        return response.choices[0].message.content
    
    async def handle(self, messages: discord.Message, context: List[discord.Message]) -> str:
        prompt = await context_to_prompt(context)
        prompt.insert(0, SystemMessage(content=SYSTEM_PROMPT))
        prompt.append(UserMessage(content=messages.content))

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=prompt,
        )

        if not response.choices:
            return ERROR_RESPONSE
        return str(response.choices[0].message.content)


Agent = AgentModel()
