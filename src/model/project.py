from typing import List
from beanie import Document, Link
from .task import Task
from .user import User


class Project(Document):
    name: str
    owner: Link[User]

    users: List[Link[User]] = []
    tasks: List[Link[Task]] = []
    objects: List[str] = []

    class Meta:
        collection = "projects"
