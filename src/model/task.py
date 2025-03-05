from datetime import datetime
from typing import Optional
from beanie import Document, PydanticObjectId


class Task(Document):
    name: str
    description: Optional[str] = None
    project: PydanticObjectId

    owner: PydanticObjectId

    deadline: Optional[datetime]
    completed: bool = False

    class Meta:
        collection = "tasks"
