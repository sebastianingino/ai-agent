import base64
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from result import as_result

from mistral.chat import Chat
from parsers import content as content_parser


@as_result(Exception)
def when_to_datetime(when: str) -> datetime:
    """Converts natural language "when" to a datetime"""

    class DateTime(BaseModel):
        dt: str

    client = Chat.client
    response = client.chat.parse(
        model="mistral-small-latest",
        messages=[
            {
                "role": "system",
                "content": f"Convert a natural language 'when' to a ISO-format datetime. The current datetime is {datetime.now().isoformat()}.",
            },
            {"role": "user", "content": when},
        ],
        response_format=DateTime,
    )

    if (
        response.choices
        and response.choices[0].message
        and response.choices[0].message.parsed
    ):
        return datetime.fromisoformat(response.choices[0].message.parsed.dt)

    raise ValueError("Failed to parse 'when' to a datetime")


@as_result(Exception)
def datetime_to_when(dt: datetime) -> str:
    """Converts a datetime to natural language "when" """

    class When(BaseModel):
        when: str

    client = Chat.client
    response = client.chat.parse(
        model="mistral-small-latest",
        messages=[
            {
                "role": "system",
                "content": f"""
                Convert a ISO-format datetime to a natural language 'when'. The current datetime is {datetime.now().isoformat()}.
                For example, {datetime.now().date() + timedelta(days=1)} can be converted to "tomorrow" and {datetime.now().date() + timedelta(days=7)} can be converted to "next {datetime.now().date() + timedelta(days=7):%A}".
                If the date is far in the future but still within the same year, you can use the month and day, e.g. "July 4th".
                If the date is really far in the future, you can use the year, month, and day, e.g. "July 4th, 2030".
                """.strip(),
            },
            {"role": "user", "content": f"{dt.isoformat()}"},
        ],
        response_format=When,
    )

    if (
        response.choices
        and response.choices[0].message
        and response.choices[0].message.parsed
    ):
        return response.choices[0].message.parsed.when

    raise ValueError("Failed to convert datetime to 'when'")


@as_result(Exception)
def import_project(content: content_parser.Content):
    class Task(BaseModel):
        name: str
        description: Optional[str]
        deadline: Optional[str]

    class Project(BaseModel):
        name: str
        description: Optional[str]
        tasks: List[Task]
        deadline: Optional[str]

    user_content = [{"type": "text", "text": content["content"]}]
    for test_attachment in content["text_attachments"]:
        user_content.append({"type": "text", "text": test_attachment})
    for image_attachment in content["image_attachments"]:
        user_content.append(
            {
                "type": "image_url",
                "image_url": f"data:image/png;base64,{base64.b64encode(image_attachment).decode()}",
            }
        )

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
        return response.choices[0].message.parsed

    raise ValueError("Failed to import project")
