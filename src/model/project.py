from typing import List
from beanie import Document, Link, PydanticObjectId
from .task import Task


class Project(Document):
    name: str
    owner: PydanticObjectId

    members: List[PydanticObjectId] = []
    admins: List[PydanticObjectId] = []

    tasks: List[Link[Task]] = []
    objects: List[str] = []

    class Meta:
        collection = "projects"
