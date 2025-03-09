from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Optional, Union
import discord.ext.commands
from pydantic import BaseModel
from result import Result

from commands.command import CommandContext
from model.user import User


@dataclass
class ActionContext:
    user: User
    bot: discord.Client


Context = Union[ActionContext, CommandContext]


class Action(ABC, BaseModel):
    _memo: Dict[str, Any] = {}
    _preflighted: bool = False

    def __init__(self, **data):
        _memo = {}
        super().__init__(**data)

    def __init_subclass__(cls, **kwargs):
        preflight_func = cls.preflight

        def preflight(self, ctx: Context):
            self._preflighted = True
            return preflight_func(self, ctx)

        cls.preflight = preflight

        execute_func = cls.execute

        def execute(self, ctx: Context):
            if not self._preflighted:
                raise Exception("Preflight not run.")
            return execute_func(self, ctx)

        cls.execute = execute

    unsafe: ClassVar[bool]
    effective: ClassVar[bool]

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

    @abstractmethod
    def __str__(self) -> str:
        pass

    @classmethod
    def tool_schema(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": cls.__name__,
                "description": cls.__doc__.strip() if cls.__doc__ else "",
                "parameters": {
                    "type": "object",
                    "properties": {
                        k: v
                        for k, v in cls.model_json_schema()["properties"].items()
                        if k != "_memo"
                    },
                    "required": [
                        k
                        for k, v in cls.model_json_schema()["properties"].items()
                        if k != "_memo" and v.get("type")
                    ],
                },
            },
        }
