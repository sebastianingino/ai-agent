from datetime import datetime, timedelta
from pydantic import BaseModel
from result import as_result
from mistral.chat import Chat

MISTRAL_MODEL = "mistral-small-latest"


@as_result(Exception)
def when_to_datetime(when: str) -> datetime:
    """Converts natural language "when" to a datetime"""

    class DateTime(BaseModel):
        dt: str

    client = Chat.client
    response = client.chat.parse(
        model=MISTRAL_MODEL,
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
        model=MISTRAL_MODEL,
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
def title_document(content: str) -> str:
    """Title a document"""

    class Title(BaseModel):
        title: str

    client = Chat.client
    response = client.chat.parse(
        model=MISTRAL_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Please give the following document a title.",
            },
            {"role": "user", "content": content},
        ],
        response_format=Title,
    )

    if (
        response.choices
        and response.choices[0].message
        and response.choices[0].message.parsed
    ):
        return response.choices[0].message.parsed.title

    raise ValueError("Failed to title document")
