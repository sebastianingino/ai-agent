from typing import Optional
from beanie import Document, PydanticObjectId

class User(Document):
    default_project: Optional[PydanticObjectId] = None
