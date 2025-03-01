from typing import ClassVar, List, Optional
import discord
from result import Err, Ok, Result

from model.project import Project
from model.user import User
from actions.action import Action, Context


class ProjectNew(Action):
    name: str
    description: Optional[str] = None

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, Project]:
        for project in ctx.user.projects:
            if project.name == self.name:  # type: ignore
                return Err(project)  # type: ignore
        return Ok(None)

    def preflight_wrap(self, result: Result[None, Project]) -> Result[None, str]:
        if result.is_err():
            return Err(f"Project {self.name} already exists.")
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[Project, Exception]:
        try:
            project = Project(
                name=self.name, owner=ctx.user.id, description=self.description
            )
            project.members.append(ctx.user.id)
            ctx.user.projects.append(project)
            await project.save()
            await ctx.user.save()
            return Ok(project)
        except Exception as e:
            return Err(e)

    def execute_wrap(self, result: Result[Project, Exception]) -> Result[str, str]:
        if result.is_err():
            return Err("Failed to create project.")
        return Ok(f"Project {self.name} created.")


class ProjectList(Action):
    effective: ClassVar[bool] = False
    unsafe: ClassVar[bool] = False

    async def preflight(self, _: Context) -> Result[None, None]:
        return Ok(None)

    def preflight_wrap(self, _: Result[None, None]) -> Result[None, str]:
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[str, str]:
        if len(ctx.user.projects) == 0:
            return Ok("No projects found.")
        return Ok(
            "**Projects:**\n"
            + "\n".join(
                f"{'⭐ ' if project == ctx.user.default_project else ''}{project.name}"  # type: ignore
                for project in ctx.user.projects
            )
        )

    def execute_wrap(self, result: Result[str, str]) -> Result[str, str]:
        if result.is_err():
            return Err("Failed to list projects.")
        return Ok(result.unwrap())


class ProjectInfo(Action):
    name: str

    effective: ClassVar[bool] = False
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, None]:
        for project in ctx.user.projects:
            if project.name == self.name:  # type: ignore
                owner = await User.find_one(User.id == project.owner)  # type: ignore
                if not owner:
                    return Err(None)
                discord_owner = ctx.bot.get_user(owner.discord_id)
                if not discord_owner:
                    return Err(None)
                self._memo["project"] = project
                self._memo["owner"] = discord_owner
        return Ok(None)

    def preflight_wrap(self, result: Result[None, None]) -> Result[None, str]:
        if result.is_err():
            return Err(f"Project {self.name} not found.")
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[str, str]:
        project = self._memo["project"]
        owner = self._memo["owner"]
        members: List[discord.User] = []
        for member in project.members:  # type: ignore
            user = await User.find_one(User.id == member)
            if user and (discord_user := ctx.bot.get_user(user.discord_id)):
                members.append(discord_user)

        return Ok(
            f"**{project.name}**\n"
            f"Owner: {owner.mention}\n"
            f"Members: {', '.join(member.mention for member in members)}",
        )

    def execute_wrap(self, result: Result[str, str]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Failed to get info for project {self.name}")
        return Ok(result.unwrap())


class ProjectDelete(Action):
    name: str

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = True

    async def preflight(self, ctx: Context) -> Result[None, None]:
        project = await Project.find_one(
            Project.name == self.name, Project.owner == ctx.user.id
        )
        if not project:
            return Err(None)
        self._memo["project"] = project
        return Ok(None)

    def preflight_wrap(self, result: Result[None, None]) -> Result[None, str]:
        if result.is_err():
            return Err(f"Project {self.name} not found.")
        return Ok(None)

    async def execute(self, _: Context) -> Result[None, None]:
        project = self._memo["project"]
        await project.delete()
        return Ok(None)

    def execute_wrap(self, result: Result[None, None]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Failed to delete project {self.name}.")
        return Ok(f"Project {self.name} deleted.")


class ProjectInvite(Action):
    name: str
    users: List[int]

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, None]:
        project = await Project.find_one(
            Project.name == self.name, Project.owner == ctx.user.id
        )
        if not project:
            return Err(None)
        self._memo["project"] = project
        return Ok(None)

    def preflight_wrap(self, result: Result[None, None]) -> Result[None, str]:
        if result.is_err():
            return Err(f"Project {self.name} not found.")
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[List[discord.User], None]:
        project = self._memo["project"]
        mentions: List[discord.User] = []
        for user in self.users:
            user_model = await User.find_one(User.discord_id == user)
            if not user_model:
                user_model = User(discord_id=user)
                await user_model.insert()
            project.members.append(user_model.id)
            user_model.projects.append(project)
            await user_model.save()
            if mention := ctx.bot.get_user(user):
                mentions.append(mention)
        await project.save()

        return Ok(mentions)

    def execute_wrap(self, result: Result[List[discord.User], None]):
        if result.is_err():
            return Err(f"Failed to invite users to project {self.name}.")
        return Ok(
            f"User{'s' if len(self.users) > 1 else ''} {', '.join(user.mention for user in result.unwrap())} added to project {self.name}."
        )


class ProjectKick(Action):
    name: str
    users: List[int]

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, None]:
        project = await Project.find_one(
            Project.name == self.name, Project.owner == ctx.user.id
        )
        if not project:
            return Err(None)
        self._memo["project"] = project
        return Ok(None)

    def preflight_wrap(self, result: Result[None, None]) -> Result[None, str]:
        if result.is_err():
            return Err(f"Project {self.name} not found.")
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[List[discord.User], None]:
        project = self._memo["project"]
        mentions: List[discord.User] = []
        for user in self.users:
            user_model = await User.find_one(User.discord_id == user)
            if not user_model:
                user_model = User(discord_id=user)
                await user_model.insert()
            project.members.remove(user_model.id)
            user_model.projects.remove(project)
            await user_model.save()
            if mention := ctx.bot.get_user(user):
                mentions.append(mention)
        await project.save()

        return Ok(mentions)

    def execute_wrap(self, result: Result[List[discord.User], None]):
        if result.is_err():
            return Err(f"Failed to remove users from project {self.name}.")
        return Ok(
            f"User{'s' if len(self.users) > 1 else ''} {', '.join(user.mention for user in result.unwrap())} removed from project {self.name}."
        )


class ProjectLeave(Action):
    name: str

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = True

    async def preflight(self, ctx: Context) -> Result[None, str]:
        for project in ctx.user.projects:
            print(project)
            if project.name == self.name:  # type: ignore
                if project.owner == ctx.user.id:  # type: ignore
                    return Err("Sorry, you can't leave a project you own. Use `!project delete` instead.")
                self._memo["project"] = project
                return Ok(None)
        return Err(f"Project {self.name} not found.")

    def preflight_wrap(self, result: Result[None, str]) -> Result[None, str]:
        return result

    async def execute(self, ctx: Context) -> Result[None, Exception]:
        project = self._memo["project"]
        try:
            ctx.user.projects.remove(project)
            project.members.remove(ctx.user.id)
            await ctx.user.save()
            await project.save()
            return Ok(None)
        except Exception as e:
            return Err(e)
    
    def execute_wrap(self, result: Result[None, Exception]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Failed to leave project {self.name}.")
        return Ok(f"Left project {self.name}.")
