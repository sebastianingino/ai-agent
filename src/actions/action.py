from abc import ABCMeta, abstractmethod
from pydantic import BaseModel
from result import Result,

from model.user import User



class Action(BaseModel, metaclass=ABCMeta):
    @property
    @abstractmethod
    def unsafe(self) -> bool:
        pass

    @property
    @abstractmethod
    def effective(self) -> bool:
        pass

    @abstractmethod
    async def preflight(self, user: User) -> Result[None, str]:
        pass

    @abstractmethod
    async def execute(self, user: User) -> bool:
        pass
