from datetime import datetime
from typing import ClassVar, List, Optional
import discord
from result import Err, Ok, Result

from mistral import functions, rag
from model.project import Project
from model.user import User
from actions.action import Action, Context


class ProjectNew(Action):
    """
    Create a new project. The project name must be unique.
    """

    name: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, Project]:
        for project in ctx.user.projects:
            if project.name.lower() == self.name.lower():  # type: ignore
                return Err(project)  # type: ignore
        return Ok(None)

    def preflight_wrap(self, result: Result[None, Project]) -> Result[None, str]:
        if result.is_err():
            return Err(f"Project {self.name} already exists.")
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[Project, Exception]:
        if not ctx.user.id:
            return Err(Exception("User not found."))
        try:
            project = Project(
                name=self.name,
                owner=ctx.user.id,
                description=self.description,
                deadline=self.deadline,
            )
            project.members.append(ctx.user.id)
            ctx.user.projects.append(project)  # type: ignore
            await project.save()
            await ctx.user.save()
            return Ok(project)
        except Exception as e:
            return Err(e)

    def execute_wrap(self, result: Result[Project, Exception]) -> Result[str, str]:
        if result.is_err():
            return Err("Failed to create project.")
        return Ok(f"Project {self.name} created.")

    def __str__(self) -> str:
        if self.deadline:
            when = functions.datetime_to_when(self.deadline).unwrap_or(None)
        else:
            when = None
        return f"**New project**: {self.name}{f' - {self.description}' if self.description else ''}{f' *(due {when})*' if when else ''}"


class ProjectList(Action):
    """
    List all projects.
    """

    effective: ClassVar[bool] = False
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, None]:
        return Ok(None)

    def preflight_wrap(self, result: Result[None, None]) -> Result[None, str]:
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

    def __str__(self) -> str:
        return "**List projects**"


class ProjectInfo(Action):
    """
    Get information about a project.
    """

    name: str

    effective: ClassVar[bool] = False
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, None]:
        for project in ctx.user.projects:
            if project.name.lower() == self.name.lower():  # type: ignore
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

    def __str__(self) -> str:
        return f"**Info** for project {self.name}"


class ProjectDeadline(Action):
    """
    Set the deadline for a project.
    """

    when: str
    project: Optional[str] = None

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, str]:
        datetime = functions.when_to_datetime(self.when)
        if datetime.is_err():
            return Err(f"Failed to parse date: {datetime.unwrap_err()}")
        self._memo["datetime"] = datetime.unwrap()

        if self.project:
            for project in ctx.user.projects:
                if project.name.lower() == self.project.lower():  # type: ignore
                    self._memo["project"] = project
                    return Ok(None)
            return Err(f"Project {self.project} not found.")

        if ctx.user.default_project:
            self._memo["project"] = ctx.user.default_project
            return Ok(None)
        return Err("No default project found.")

    def preflight_wrap(self, result: Result[None, str]) -> Result[None, str]:
        return result

    async def execute(self, ctx: Context) -> Result[Optional[datetime], str]:
        project = self._memo["project"]
        deadline = self._memo["datetime"]

        previous_deadline = project.deadline
        if previous_deadline and previous_deadline == deadline:
            return Err(f"Project {project.name} already has a deadline of {deadline}.")
        project.deadline = deadline
        await project.save()
        return Ok(previous_deadline)

    def execute_wrap(self, result: Result[Optional[datetime], str]) -> Result[str, str]:
        project = self._memo["project"]
        if result.is_err():
            return Err(result.unwrap_err())
        previous_deadline = result.unwrap()
        if previous_deadline is None:
            return Ok(f"Set deadline for project {project.name} to {self.when}.")
        previous_deadline_text = functions.datetime_to_when(
            previous_deadline
        ).unwrap_or(previous_deadline.strftime("%Y-%m-%d %H:%M:%S"))
        return Ok(
            f"Changed deadline for project {project.name} from {previous_deadline_text} to {self.when}."
        )

    def __str__(self) -> str:
        return f"**Set Deadline** for project to {self.when}"


class ProjectDelete(Action):
    """
    Delete a project.
    """

    name: str

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = True

    async def preflight(self, ctx: Context) -> Result[None, None]:
        projects = Project.find(Project.owner == ctx.user.id)
        project = None
        async for p in projects:
            if p.name.lower() == self.name.lower():
                project = p
                break
        if not project:
            return Err(None)
        self._memo["project"] = project
        return Ok(None)

    def preflight_wrap(self, result: Result[None, None]) -> Result[None, str]:
        if result.is_err():
            return Err(f"Project {self.name} not found.")
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[None, None]:
        project = self._memo["project"]
        for task in project.tasks:
            await task.delete()
        for document in project.documents:
            await rag.delete_documents(document.document_ids)
            await document.delete()
        if ctx.user.default_project == project:
            ctx.user.default_project = None
        ctx.user.projects.remove(project)
        await ctx.user.save()
        await project.delete()
        return Ok(None)

    def execute_wrap(self, result: Result[None, None]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Failed to delete project {self.name}.")
        return Ok(f"Project {self.name} deleted.")

    def __str__(self) -> str:
        return f"**Delete project** {self.name}"


class ProjectInvite(Action):
    """
    Invite users to a project.
    """

    name: str
    users: List[int]

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, None]:
        project = await Project.find_one(
            Project.name.lower() == self.name.lower(), Project.owner == ctx.user.id
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
            if user_model.id not in project.members:
                project.members.append(user_model.id)
            if project not in user_model.projects:
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

    def __str__(self) -> str:
        return f"**Invite users** to project {self.name}"


class ProjectKick(Action):
    """
    Kick users from a project.
    """

    name: str
    users: List[int]

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, None]:
        project = await Project.find_one(
            Project.name.lower() == self.name.lower(), Project.owner == ctx.user.id
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
            if user_model.id in project.members:
                project.members.remove(user_model.id)
            if project in user_model.projects:
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

    def __str__(self) -> str:
        return f"**Kick users** from project {self.name}"


class ProjectLeave(Action):
    """
    Leave a project.
    """

    name: str

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = True

    async def preflight(self, ctx: Context) -> Result[None, str]:
        for project in ctx.user.projects:
            if project.name.lower() == self.name.lower():  # type: ignore
                if project.owner == ctx.user.id:  # type: ignore
                    return Err(
                        "Sorry, you can't leave a project you own. Use `!project delete` instead."
                    )
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

    def __str__(self) -> str:
        return f"**Leave project** {self.name}"


class ProjectSetDefault(Action):
    """
    Set the default project.
    """

    name: str

    effective: ClassVar[bool] = False
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, None]:
        for project in ctx.user.projects:
            if project.name.lower() == self.name.lower():  # type: ignore
                self._memo["project"] = project
                return Ok(None)
        return Err(None)

    def preflight_wrap(self, result: Result[None, None]) -> Result[None, str]:
        if result.is_err():
            return Err(f"Project {self.name} not found.")
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[None, None]:
        project = self._memo["project"]
        ctx.user.default_project = project
        await ctx.user.save()
        return Ok(None)

    def execute_wrap(self, result: Result[None, None]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Failed to set project {self.name} as default.")
        return Ok(f"Project {self.name} set as default.")

    def __str__(self) -> str:
        return f"Set project {self.name} as default"
