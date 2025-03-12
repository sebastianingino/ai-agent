import json
import logging
import os
from beanie import PydanticObjectId
import discord
from typing import List, Optional, Type
from mistralai import Mistral, SystemMessage, UserMessage
from datetime import datetime
from pydantic import BaseModel
from actions.action import Action, apply_multiple
from actions.document import (
    DocumentAdd,
    DocumentRemove,
    DocumentSearch,
    DocumentSearchAll,
)
from actions.project import (
    ProjectDeadline,
    ProjectDelete,
    ProjectLeave,
    ProjectNew,
    ProjectSetDefault,
)
from actions.task import TaskDeadline, TaskDelete, TaskMark, TaskNew
from model.user import User
from response.ButtonResponse import binary_response
from util.messages import context_to_prompt

MISTRAL_MODEL = "mistral-small-latest"
SYSTEM_PROMPT = """You are a helpful and friendly project manager assistant named Discoin. You help users manage their projects and tasks. 
You have access to all the information about the user and their projects. You can also perform actions on the user's behalf.
You can create, update, and delete tasks and projects. You can also mark tasks as completed or not completed. You can also leave a shared project and set a project as default.
You can also set deadlines for tasks and projects. Note that you can't invite or kick people from projects, but you can tell them to do so if needed using the `!project invite` and `!project kick` commands. Only mention this if the user specifically asks for it.
You can also add, remove, and search for documents in a project. You can also search for documents across all projects.
Please keep responses relevant to the user's projects and tasks, and avoid discussing unrelated topics. Keep responses polite, short, and concise. You should still be friendly and helpful.
If you don't know the answer, say "I don't know" or "I can't help with that". If no answer exists when looking up documents, tell the user that you couldn't find any relevant information. If you do find relevant information in one or many documents, please cite which document titles you found the information in.
You can also ask the user for more information if needed.
Please use relative dates when possible, e.g. "tomorrow", "this Thursday", "next week", etc. If something is further away, use absolute dates and times. You may omit the time if it's not relevant.
You are provided the context of the conversation, including the user's messages and the bot's responses. Each message contains the timestamp in ISO format at the beginning. You should not include a message timestamp in your response.
If the user asks what you can do, tell them that you can help them manage their projects and tasks, and that you can perform actions on their behalf. Also tell them that they can perform actions by hand if they prefer and to use `!help` for more information.
"""
OTHER_USERS_MESSAGE = "Some of the messages in the context are from other users and are marked as such. Please note that the current user may or may not be able to see the projects and tasks of other users."
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
    DocumentAdd,
    DocumentRemove,
    DocumentSearch,
    DocumentSearchAll,
]
TOOLS = [action.tool_schema() for action in ACTIONS]
TOOL_NAMES = {action.__name__: action for action in ACTIONS}

LOGGER = logging.getLogger(__name__)


class TaskObject(BaseModel):
    _id: PydanticObjectId
    name: str
    completed: bool
    description: Optional[str] = None

    deadline: Optional[datetime] = None


class ProjectObject(BaseModel):
    _id: PydanticObjectId
    name: str
    is_owner: bool
    description: Optional[str] = None

    deadline: Optional[datetime] = None

    tasks: List[TaskObject] = []
    documents: List[str] = []


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
                _id=project.id,  # type: ignore
                name=project.name,  # type: ignore
                description=project.description,  # type: ignore
                is_owner=project.owner == user.id,  # type: ignore
                deadline=project.deadline,  # type: ignore
                documents=[],
                tasks=[],
            )

            for task in project.tasks:  # type: ignore
                task_object = TaskObject(
                    _id=task.id,
                    name=task.name,
                    description=task.description,
                    completed=task.completed,
                    deadline=task.deadline,
                )
                project_object.tasks.append(task_object)

            for document in project.documents:  # type: ignore
                project_object.documents.append(document.title)

            user_object.projects.append(project_object)

        return user_object.model_dump_json()

    async def handle(
        self,
        message: discord.Message,
        context: List[discord.Message],
        bot: discord.Client,
    ) -> Optional[str]:
        prompt, other_users = context_to_prompt(context, message.author)
        prompt.append(SystemMessage(content=SYSTEM_PROMPT))
        if other_users:
            prompt.append(SystemMessage(content=OTHER_USERS_MESSAGE))

        user = await User.find_one(
            User.discord_id == message.author.id, fetch_links=True
        )
        if not user:
            user = User(discord_id=message.author.id)
            await user.insert()
        prompt.append(
            SystemMessage(content=f"User status: \n{await self.get_user_status(user)}")
        )
        prompt.append(
            SystemMessage(
                content=f"The current datetime is {datetime.now().isoformat()}"
            )
        )

        user_message = f"({message.created_at.isoformat()}) {message.content}"
        if len(message.attachments) > 0:
            user_message += f"\nAttached URLs: {' '.join(attachment.url for attachment in message.attachments)}"
        prompt.append(UserMessage(content=user_message))

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=prompt,
            tools=TOOLS,  # type: ignore
            tool_choice="auto",
        )

        if not response.choices:
            return ERROR_RESPONSE

        if response.choices[0].message.tool_calls:
            unsafe, effective = False, False
            actions: List[Action] = []

            async def callback(interaction: discord.Interaction):
                async with message.channel.typing():
                    result = await apply_multiple(
                        actions, interaction.user, interaction.client
                    )
                    if result.is_err():
                        return await message.reply(
                            f"Error executing actions: {result.unwrap_err()}"
                        )
                    prompt.append(
                        SystemMessage(content="Actions executed successfully")
                    )
                    response = await self.client.chat.complete_async(
                        model=MISTRAL_MODEL,
                        messages=prompt,
                    )
                    if not response.choices:
                        return ERROR_RESPONSE
                    await message.reply(str(response.choices[0].message.content))

            for tool_call in response.choices[0].message.tool_calls:
                action = TOOL_NAMES.get(tool_call.function.name)
                if not action:
                    continue
                try:
                    args = (
                        json.loads(tool_call.function.arguments)
                        if isinstance(tool_call.function.arguments, str)
                        else tool_call.function.arguments
                    )
                    actions.append(action(**args))
                    unsafe = unsafe or action.unsafe
                    effective = effective or action.effective
                except Exception as e:
                    LOGGER.error(
                        f"Error while parsing tool call {tool_call.function.name}: {e}"
                    )
                    return ERROR_RESPONSE

            if unsafe:
                await message.reply(
                    f"""
Careful! This can't be undone. Are you sure you want to proceed?

This will execute the following actions:
{"\n".join([f"- {str(action)}" for action in actions])}
                    """.strip(),
                    view=binary_response(callback, user=message.author, reverse=True),
                )
                return None

            result = await apply_multiple(
                actions,
                message.author,
                bot,
            )
            if result.is_err():
                return f"Error executing actions: {result.unwrap_err()}"
            prompt.append(SystemMessage(content="Actions executed successfully"))
            response = await self.client.chat.complete_async(
                model=MISTRAL_MODEL,
                messages=prompt,
            )
            if not response.choices:
                return ERROR_RESPONSE
            return str(response.choices[0].message.content)

        return str(response.choices[0].message.content)


Agent = AgentModel()
