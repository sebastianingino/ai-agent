import logging
from typing import Any, Callable, Coroutine, Dict, Tuple

import discord

AsyncCallable = Callable[..., Coroutine[Any, Any, Any]]

LOGGER = logging.getLogger(__name__)

class _Reactions:
    handlers: Dict[int, Dict[str, Tuple[AsyncCallable, Tuple]]]
    use_parent: Dict[int, bool]

    def __init__(self):
        self.handlers = {}
        self.use_parent = {}

    def register_handler(
        self,
        message: discord.Message,
        reaction: str,
        callback: AsyncCallable,
        *args,
        use_parent: bool = True,
    ):
        if message.id not in self.handlers:
            self.handlers[message.id] = {}
        self.handlers[message.id][reaction] = (callback, args)
        self.use_parent[message.id] = use_parent

    def unregister_handler(self, message: discord.Message):
        self.handlers.pop(message.id, None)

    def unregister_handler_by_reaction(self, message: discord.Message, reaction: str):
        if message.id in self.handlers:
            self.handlers[message.id].pop(reaction, None)

    async def handle(
        self, reaction: discord.Reaction, message: discord.Message, user: discord.User
    ) -> bool:
        if message.id not in self.handlers:
            if (
                message.reference
                and (parent := message.reference.resolved)
                and isinstance(parent, discord.Message)
                and parent.id in self.handlers
                and self.use_parent[parent.id]
                and user.id == parent.author.id
            ):
                LOGGER.debug(f"Using parent message {parent.id} for reaction {message.id}")
                message = parent
            else:
                LOGGER.debug(f"No handlers for message {message.id}")
                return False

        reactions = self.handlers[message.id]

        if str(reaction.emoji) in reactions:
            callback, args = reactions[str(reaction.emoji)]
            LOGGER.debug(f"Handled reaction {reaction.emoji} on message {message.id}")
            self.unregister_handler(message)
            await callback(message, user, *args)
            return True

        LOGGER.debug(f"No handler for reaction {reaction.emoji} on message {message.id}")
        return False

    def has_handler(self, message: discord.Message):
        return message.id in self.handlers
