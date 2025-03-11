from datetime import datetime
from typing import List, Optional
from beanie import Document, Link, PydanticObjectId
from model.document import EmbeddedDocument
from model.task import Task


class Project(Document):
    name: str
    description: Optional[str] = None
    owner: PydanticObjectId

    members: List[PydanticObjectId] = []
    admins: List[PydanticObjectId] = []

    tasks: List[Link[Task]] = []
    documents: List[EmbeddedDocument] = []

    deadline: Optional[datetime] = None

    class Meta:
        collection = "projects"
