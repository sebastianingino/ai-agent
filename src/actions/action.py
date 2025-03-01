from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Annotated, Any, Dict, Union
import discord
from pydantic import BaseModel, Field
from result import Result

from commands.command import CommandContext
from model.user import User


@dataclass
class ActionContext:
    user: User
    bot: discord.ext.commands.Bot


Context = Union[ActionContext, CommandContext]


class Action(ABC, BaseModel):
    _memo: Dict[str, Any] = {}
    _preflighted: bool = False

    def __init__(self, **data):
        _memo = {}
        super().__init__(**data)

    def __init_subclass__(cls, **kwargs):
        preflight_func = cls.preflight

        def preflight(self, user: User):
            self._preflighted = True
            return preflight_func(self, user)

        cls.preflight = preflight

        execute_func = cls.execute

        def execute(self, user: User):
            if not self._preflighted:
                raise Exception("Preflight not run.")
            return execute_func(self, user)

        cls.execute = execute

    @property
    @abstractmethod
    def unsafe(self) -> Annotated[bool, Field(exclude=True)]:
        pass

    @property
    @abstractmethod
    def effective(self) -> Annotated[bool, Field(exclude=True)]:
        pass

    @abstractmethod
    async def preflight(self, ctx: Context) -> Result[Any, Any]:
        pass

    @abstractmethod
    def preflight_wrap(self, result: Result[Any, Any]) -> Result[None, str]:
        pass

    @abstractmethod
    async def execute(self, ctx: Context) -> Result[Any, Any]:
        pass

    @abstractmethod
    def execute_wrap(self, result: Result[Any, Any]) -> Result[str, str]:
        pass
