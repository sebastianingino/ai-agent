from datetime import datetime
from typing import ClassVar, Optional

from result import Err, Ok, Result
from actions.action import Action, Context
from mistral import functions
from model.project import Project
from model.task import Task


class TaskNew(Action):
    name: str
    project: Optional[str] = None

    description: Optional[str] = None
    deadline: Optional[datetime] = None

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, None]:
        if not self.project:
            if not ctx.user.default_project:
                return Err(None)
            self._memo["project"] = ctx.user.default_project
            return Ok(None)

        for project in ctx.user.projects:
            if project.name.lower() == self.project.lower():  # type: ignore
                self._memo["project"] = project
                return Ok(None)
        return Err(None)

    def preflight_wrap(self, result: Result[None, None]) -> Result[None, str]:
        if result.is_err():
            return Err(f"Project {self.project} not found.")
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[Task, Exception]:
        if not ctx.user.id:
            return Err(Exception("User not found."))
        project = self._memo["project"]
        try:
            task = Task(
                name=self.name,
                description=self.description,
                project=project.id,
                deadline=self.deadline,
                owner=ctx.user.id,
            )
            project.tasks.append(task)

            await task.insert()
            await project.save()
            return Ok(task)
        except Exception as e:
            return Err(e)

    def execute_wrap(self, result: Result[Task, Exception]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Error creating task: {result.unwrap_err()}")
        return Ok(f"Task {result.unwrap().name} created.")

    def __str__(self) -> str:
        if self.deadline:
            when = functions.datetime_to_when(self.deadline).unwrap_or(None)
        else:
            when = None
        return f"**New task**: {self.name}{f" - {self.description}" if self.description else ''}{f" *(due {when})*" if when else ''}"


class TaskMark(Action):
    task: str
    status: bool
    project: Optional[str]

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[Task, str]:
        project = None
        if not self.project:
            if not ctx.user.default_project:
                return Err("Default project not found.")
            project = ctx.user.default_project
        else:
            for p in ctx.user.projects:
                if p.name == self.project:  # type: ignore
                    project = project

        if not project:
            return Err("Project not found.")

        for task in project.tasks:  # type: ignore
            if task.name.lower() == self.task.lower():
                self._memo["task"] = task
                return Ok(task)
        return Err(f"Task {self.task} not found.")

    def preflight_wrap(self, result: Result[Task, str]) -> Result[None, str]:
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[Task, Exception]:
        task = self._memo["task"]
        task.completed = self.status
        try:
            await task.save()
            return Ok(task)
        except Exception as e:
            return Err(e)

    def execute_wrap(self, result: Result[Task, Exception]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Error marking task: {result.unwrap_err()}")
        return Ok(
            f"Task {result.unwrap().name} marked as {'completed' if self.status else 'incomplete'}."
        )

    def __str__(self) -> str:
        return f"**Mark task** as {'completed' if self.status else 'incomplete'}"


class TaskDelete(Action):
    task: str
    project: Optional[str]

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = True

    async def preflight(self, ctx: Context) -> Result[Task, str]:
        project = None
        if not self.project:
            if not ctx.user.default_project:
                return Err("Default project not found.")
            project = ctx.user.default_project
        else:
            for p in ctx.user.projects:
                if p.name == self.project:  # type: ignore
                    project = project

        if not project:
            return Err("Project not found.")

        for task in project.tasks:  # type: ignore
            if task.name.lower() == self.task.lower():
                self._memo["task"] = task
                return Ok(task)
        return Err(f"Task {self.task} not found.")

    def preflight_wrap(self, result: Result[Task, str]) -> Result[None, str]:
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[Task, Exception]:
        task = self._memo["task"]
        try:
            await task.delete()
            return Ok(task)
        except Exception as e:
            return Err(e)

    def execute_wrap(self, result: Result[Task, Exception]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Error deleting task: {result.unwrap_err()}")
        return Ok(f"Task {result.unwrap().name} deleted.")

    def __str__(self) -> str:
        return "**Delete task**"


class TaskList(Action):
    project: Optional[str] = None

    effective: ClassVar[bool] = False
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, str]:
        if not self.project:
            if not ctx.user.default_project:
                return Err("Default project not found.")
            self._memo["project"] = ctx.user.default_project
            return Ok(None)
        for project in ctx.user.projects:
            if project.name.lower() == self.project.lower():  # type: ignore
                self._memo["project"] = project
                return Ok(None)
        return Err(f"Project {self.project} not found.")

    def preflight_wrap(self, result: Result[Project, str]) -> Result[None, str]:
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[str, Exception]:
        project = self._memo["project"]
        if len(project.tasks) == 0:
            return Ok(f"No tasks found for {project.name}.")
        tasks = []
        for task in project.tasks:
            when = functions.datetime_to_when(task.deadline)
            deadline = when.unwrap_or(task.deadline.strftime("%Y-%m-%d %H:%M"))
            tasks.append(f"- {"✅" if task.completed else ""} {task.name} ({deadline})")

        return Ok(f"**Tasks for {project.name}**:\n" + "\n".join(tasks))

    def execute_wrap(self, result: Result[str, Exception]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Error listing tasks: {result.unwrap_err()}")
        return Ok(result.unwrap())

    def __str__(self) -> str:
        return f"**List tasks** for {self.project}"


class TaskDeadline(Action):
    task: str
    when: str
    project: Optional[str] = None

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[Task, str]:
        datetime = functions.when_to_datetime(self.when)
        if datetime.is_err():
            return Err(f"Failed to parse date: {datetime.unwrap_err()}")
        self._memo["datetime"] = datetime.unwrap()

        project = None
        if not self.project:
            if not ctx.user.default_project:
                return Err("Default project not found.")
            project = ctx.user.default_project
        else:
            for p in ctx.user.projects:
                if p.name == self.project:  # type: ignore
                    project = project

        if not project:
            return Err("Project not found.")

        for task in project.tasks:  # type: ignore
            if task.name.lower() == self.task.lower():
                self._memo["task"] = task
                return Ok(task)
        return Err(f"Task {self.task} not found.")

    def preflight_wrap(self, result: Result[Task, str]) -> Result[None, str]:
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[Optional[datetime], Exception]:
        task = self._memo["task"]

        previous_deadline = task.deadline
        if previous_deadline and previous_deadline == task.deadline:
            Err(f"Task {task.name} already has deadline {previous_deadline}")
        task.deadline = self._memo["datetime"]
        try:
            await task.save()
            return Ok(previous_deadline)
        except Exception as e:
            return Err(e)

    def execute_wrap(
        self, result: Result[Optional[datetime], Exception]
    ) -> Result[str, str]:
        if result.is_err():
            return Err(f"Error setting deadline: {result.unwrap_err()}")
        previous_deadline = result.unwrap()
        task = self._memo["task"]
        if previous_deadline is None:
            return Ok(f"Set deadline for {task.name} to {self.when}")
        previous_deadline_text = functions.datetime_to_when(
            previous_deadline
        ).unwrap_or(previous_deadline.strftime("%Y-%m-%d %H:%M:%S"))
        return Ok(
            f"Changed deadline for {task.name} from {previous_deadline_text} to {self.when}"
        )

    def __str__(self) -> str:
        return f"**Set deadline** to {self.when}"


class TaskListAll(Action):
    effective: ClassVar[bool] = False
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, str]:
        return Ok(None)

    def preflight_wrap(self, result: Result[None, str]) -> Result[None, str]:
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(None)

    async def execute(self, ctx: Context) -> Result[str, Exception]:
        tasks = await Task.find(Task.owner == ctx.user.id).to_list()
        if len(tasks) == 0:
            return Ok("No tasks found.")
        result = []
        for task in tasks:
            if task.deadline:
                when = functions.datetime_to_when(task.deadline)
                deadline = when.unwrap_or(task.deadline.strftime("%Y-%m-%d %H:%M"))
                result.append(
                    f"- {"✅" if task.completed else ""} {task.name} ({deadline})"
                )
            else:
                result.append(f"- {"✅" if task.completed else ""} {task.name}")

        return Ok("**All Tasks**:\n" + "\n".join(result))

    def execute_wrap(self, result: Result[str, Exception]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Error listing tasks: {result.unwrap_err()}")
        return Ok(result.unwrap())

    def __str__(self) -> str:
        return "**List all tasks**"
