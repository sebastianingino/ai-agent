from typing import Annotated, List, Optional
from beanie import Document, Indexed, Link, PydanticObjectId

from .project import Project

class User(Document):
    discord_id: Annotated[int, Indexed(unique=True)]
    default_project: Optional[Link[Project]] = None

    projects: List[Link[Project]] = []
