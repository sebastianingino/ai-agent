from typing import ClassVar

from result import Err, Ok, Result

from actions.action import Action, Context


class SettingsDefaultProject(Action):
    """
    Set the default project for the user.
    """

    name: str

    effective: ClassVar[bool] = False
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, None]:
        for project in ctx.user.projects:
            if project.name == self.name:  # type: ignore
                self._memo["project"] = project
                return Ok(None)
        return Err(None)

    def preflight_wrap(self, result: Result[None, None]) -> Result[None, str]:
        if result.is_err():
            return Err(f"Project {self.name} not found.")
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[str, str]:
        ctx.user.default_project = self._memo["project"]
        await ctx.user.save()
        return Ok(f"Project {self.name} set as default.")

    def execute_wrap(self, result: Result[str, str]) -> Result[str, str]:
        return result

    def __str__(self) -> str:
        return f"**Set default project** to {self.name}"
