from typing import Callable, Dict, Tuple

import discord

class _Reactions:
    handlers: Dict[int, Dict[str, Tuple[Callable, Tuple]]] = {}

    def __init__(self):
        self.handlers = {}

    def register_handler(self, message: discord.Message, reaction: str, callback: Callable, *args):
        if message.id not in self.handlers:
            self.handlers[message.id] = {}
        self.handlers[message.id][reaction] = (callback, args)

    def unregister_handler(self, message: discord.Message):
        self.handlers.pop(message.id, None)

    def unregister_handler_by_reaction(self, message: discord.Message, reaction: str):
        if message.id in self.handlers:
            self.handlers[message.id].pop(reaction, None)

    def handle(self, reaction: discord.Reaction, message: discord.Message, user: discord.User):
        for message_id, reactions in self.handlers.items():
            if message.id == message_id:
                if str(reaction.emoji) in reactions:
                    callback, args = reactions[str(reaction.emoji)]
                    callback(message, user, *args)
                    break
        self.unregister_handler(message)
                    
    def has_handler(self, message: discord.Message):
        return message.id in self.handlers
                    
