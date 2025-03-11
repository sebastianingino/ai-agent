import base64
from datetime import datetime
from pydantic import BaseModel
from result import as_result
from actions.action import Action
from actions.project import ProjectNew
from actions.task import TaskNew
from typing import List, Optional
from mistral.chat import Chat
from parsers import content as content_parser


@as_result(Exception)
def import_project(content: content_parser.Content) -> List[Action]:
    class Task(BaseModel):
        name: str
        description: Optional[str]
        deadline: Optional[str]

    class Project(BaseModel):
        name: str
        description: Optional[str]
        tasks: List[Task]
        deadline: Optional[str]

        def to_actions(self) -> List[Action]:
            actions: List[Action] = [
                ProjectNew(
                    name=self.name,
                    description=self.description,
                    deadline=(
                        datetime.fromisoformat(self.deadline) if self.deadline else None
                    ),
                )
            ]

            for task in self.tasks:
                actions.append(
                    TaskNew(
                        name=task.name,
                        description=task.description,
                        project=self.name,
                        deadline=(
                            datetime.fromisoformat(task.deadline)
                            if task.deadline
                            else None
                        ),
                    )
                )

            return actions

    user_content = [{"type": "text", "text": content["content"]}]
    for test_attachment in content["attachments"]:
        user_content.append({"type": "text", "text": test_attachment})

    client = Chat.client
    response = client.chat.parse(
        model="mistral-small-latest",
        messages=[
            {
                "role": "system",
                "content": f"""
                You are given a specification for a project. You need to create a project with the given name, description, deadline, and tasks. Note that there may be extraneous information in the specification.
                If no project can be determined, return an empty object.
                For all deadline fields, use ISO-format datetimes strings if applicable. The current datetime is {datetime.now().isoformat()}.
                Please keep descriptions short and concise. Feel free to omit the description if it doesn't add any value.
                """,
            },
            {"role": "user", "content": user_content},
        ],
        response_format=Project,
    )

    if (
        response.choices
        and response.choices[0].message
        and response.choices[0].message.parsed
    ):
        return response.choices[0].message.parsed.to_actions()

    raise ValueError("Failed to import project")
