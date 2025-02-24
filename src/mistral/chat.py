import os
from dotenv import load_dotenv
from mistralai import Mistral, SystemMessage, UserMessage

MISTRAL_MODEL = "mistral-large-latest"
SYSTEM_PROMPT = "You are a helpful and friendly project manager assistant."
ERROR_RESPONSE = "Looks like something went wrong. Please try again later."


class ChatModel:
    client: Mistral

    def __init__(self):
        load_dotenv()
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

        self.client = Mistral(api_key=MISTRAL_API_KEY)

    async def chat(self, message: str):
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            UserMessage(content=message),
        ]

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,  # type: ignore
        )

        if response.choices:
            return response.choices[0].message.content

        return ERROR_RESPONSE

    async def help(self, help_text: str):
        messages = [
            SystemMessage(
                content=f"{SYSTEM_PROMPT} Please greet the user. This is the help text for this command: {help_text}. Please inform the user of your high-level capabilities in a sentence or two. Do not include any specific examples or instructions, but inform the user that they can use the `help` command to get more information. Do not ask the user a question."
            ),
        ]

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,  # type: ignore
        )

        if response.choices:
            return response.choices[0].message.content

        return ERROR_RESPONSE


Chat = ChatModel()
