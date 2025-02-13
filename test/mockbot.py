import logging
import weakref
import discord
from typing import Dict, Callable, Optional, Any

import discord.types
import discord.types.user
from .mockbot_ui import MockBotUI

LOGGER = logging.getLogger(__name__)


class MockState(discord.state.ConnectionState):
    messages: Dict[int, discord.Message]
    _users: weakref.WeakValueDictionary[int, discord.User]

    def __init__(self):
        self.messages = {}
        self._users = weakref.WeakValueDictionary()

    def add_message(self, message: discord.Message):
        self.messages[message.id] = message

    def _get_message(self, msg_id: Optional[int]) -> Optional[discord.Message]:
        return self.messages.get(msg_id) if msg_id else None

    def _get_guild(self, guild_id: Optional[int]) -> Optional[discord.Guild]:
        return None

class MockChannel():
    ui: MockBotUI

    def __init__(self, ui: MockBotUI):
        self.ui = ui

    async def send(self, content: str, reference: Optional[discord.Message] = None, **kwargs):
        await self.ui.write(content, role="bot")

class MockBot:
    intents: discord.Intents
    command_prefix: str

    events: Dict[str, Callable]
    commands: Dict[str, Callable]
    app: MockBotUI

    message_id: int
    state: MockState
    channel: MockChannel
    end_user: discord.types.user.User

    def __init__(self, *, intents: discord.Intents, command_prefix: str):
        self.intents = intents
        self.command_prefix = command_prefix
        self.events = {}
        self.commands = {}
        self.app = MockBotUI()

        self.message_id = 0
        self.state = MockState()
        self.channel = MockChannel(self.app)

        userPayload = discord.types.user.User(
            id=0,
            username=MockBotUI.username,
            discriminator="0000",
            avatar=None,
            global_name=MockBotUI.username,
        )
        self.end_user = userPayload

        self.user = "MockBot"

    def event(self, coro: Callable):
        self.events[coro.__name__] = coro

    def command(self, name: Optional[str] = None, help: Optional[str] = None):
        def decorator(coro):
            self.commands[name or coro.__name__] = coro

        return decorator

    async def ui_handler(self, event: Any):
        if isinstance(event, MockBotUI.OnReady):
            on_ready_msg = await self.get_event("on_ready")()
            if on_ready_msg:
                await self.app.write(on_ready_msg)
        if isinstance(event, MockBotUI.InputSubmitted):
            await self.app.write(event.value, role="user")

            data = {
                "id": self.message_id,
                "author": self.end_user,
                "content": event.value,
                "attachments": [],
                "embeds": [],
                "mentions": [],
                "edited_timestamp": None,
                "type": 0,
                "channel_id": 0,
                "pinned": False,
                "mention_everyone": False,
                "tts": False,
            }
            message = discord.Message(state=self.state, channel=self.channel, data=data)  # type: ignore
            await self.get_event("on_message")(message)

    def get_event(self, name: str):
        return self.events.get(name)

    async def process_commands(self, message: discord.Message):
        if message.content.startswith(self.command_prefix):
            command = message.content[len(self.command_prefix) :]
            if command in self.commands:
                message_content = message.content.lstrip(self.command_prefix + command).strip()
                arg = message_content if message_content and len(message_content) > 0 else None
                await self.commands[command](self.channel, arg=arg)

    def run(self, token: str):
        self.app.register_handler(self.ui_handler)
        self.app.run()
