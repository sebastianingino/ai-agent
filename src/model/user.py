from typing import Annotated, Optional
from beanie import Document, Indexed, PydanticObjectId

class User(Document):
    discord_id: Annotated[int, Indexed(unique=True)]
    default_project: Optional[PydanticObjectId]
