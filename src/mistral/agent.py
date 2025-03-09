import os
import discord
from typing import List, Optional, Type
from mistralai import Mistral, SystemMessage, UserMessage
from datetime import datetime
from pydantic import BaseModel
from actions.action import Action
from actions.project import (
    ProjectDeadline,
    ProjectDelete,
    ProjectLeave,
    ProjectNew,
    ProjectSetDefault,
)
from actions.task import TaskDeadline, TaskDelete, TaskMark, TaskNew
from model.user import User
from util.messages import context_to_prompt

MISTRAL_MODEL = "mistral-small-latest"
SYSTEM_PROMPT = """You are a helpful and friendly project manager assistant. You help users manage their projects and tasks. 
You have access to all the information about the user and their projects. You can also perform actions on the user's behalf.
You can create, update, and delete tasks and projects. You can also mark tasks as completed or not completed. You can also leave a shared project and set a project as default.
You can also set deadlines for tasks and projects. You can't invite or kick people from projects, but you can tell them to do so if needed using the `!project invite` and `!project kick` commands.
Please keep responses relevant to the user's projects and tasks, and avoid discussing unrelated topics. Keep responses short and concise.
If you don't know the answer, say "I don't know" or "I can't help with that".
You can also ask the user for more information if needed.
Please use relative dates when possible, e.g. "tomorrow", "this Thursday", "next week", etc. If something is further away, use absolute dates and times. You may omit the time if it's not relevant.
"""
ERROR_RESPONSE = "Looks like something went wrong. Please try again later."
ACTIONS: List[Type[Action]] = [
    ProjectNew,
    ProjectDeadline,
    ProjectDelete,
    ProjectLeave,
    ProjectSetDefault,
    TaskNew,
    TaskDeadline,
    TaskDelete,
    TaskMark,
]
TOOLS = [action.tool_schema() for action in ACTIONS]
TOOL_NAMES = {action.__name__: action for action in ACTIONS}

class TaskObject(BaseModel):
    name: str
    completed: bool
    description: Optional[str] = None

    deadline: Optional[datetime] = None


class ProjectObject(BaseModel):
    name: str
    is_owner: bool
    description: Optional[str] = None

    deadline: Optional[datetime] = None

    tasks: List[TaskObject] = []


class UserObject(BaseModel):
    default_project: Optional[str]
    projects: List[ProjectObject]


class AgentModel:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

        self.client = Mistral(api_key=MISTRAL_API_KEY)

    async def get_user_status(self, user: User) -> str:
        user_object = UserObject(
            default_project=user.default_project.name if user.default_project else None,  # type: ignore
            projects=[],
        )

        for project in user.projects:
            project_object = ProjectObject(
                name=project.name,  # type: ignore
                description=project.description,  # type: ignore
                is_owner=project.owner == user.id,  # type: ignore
                deadline=project.deadline,  # type: ignore
                tasks=[],
            )

            for task in project.tasks:  # type: ignore
                task_object = TaskObject(
                    name=task.name,
                    description=task.description,
                    completed=task.completed,
                    deadline=task.deadline,
                )
                project_object.tasks.append(task_object)

            user_object.projects.append(project_object)

        return user_object.model_dump_json()

    async def handle(
        self, messages: discord.Message, context: List[discord.Message]
    ) -> str:
        prompt = await context_to_prompt(context)
        prompt.append(SystemMessage(content=SYSTEM_PROMPT))

        user = await User.find_one(
            User.discord_id == messages.author.id, fetch_links=True
        )
        if not user:
            user = User(discord_id=messages.author.id)
            await user.insert()
        prompt.append(
            SystemMessage(content=f"User status: \n{await self.get_user_status(user)}")
        )
        prompt.append(
            SystemMessage(
                content=f"The current datetime is {datetime.now().isoformat()}"
            )
        )
        prompt.append(UserMessage(content=messages.content))

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=prompt,
            tools=TOOLS,  # type: ignore
            tool_choice="auto",
        )

        if not response.choices:
            return ERROR_RESPONSE
        

        unsafe = False
        actions = []
        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                action = TOOL_NAMES.get(tool_call.function.name)
                if not action:
                    continue
                try:
                    actions.append(action.model_construct(values=tool_call.function.arguments))
                except Exception:
                    return ERROR_RESPONSE
        print(actions)

        return str(response.choices[0].message.content)


Agent = AgentModel()
