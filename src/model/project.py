from datetime import datetime
from typing import List, Optional
from beanie import Document, Link, PydanticObjectId
from model.task import Task


class Project(Document):
    name: str
    owner: PydanticObjectId

    members: List[PydanticObjectId] = []
    admins: List[PydanticObjectId] = []

    tasks: List[Link[Task]] = []
    objects: List[str] = []

    deadline: Optional[datetime] = None

    class Meta:
        collection = "projects"
