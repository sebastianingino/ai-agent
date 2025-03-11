from typing import List
from beanie import Document, PydanticObjectId


class EmbeddedDocument(Document):
    title: str
    project: PydanticObjectId
    document_ids: List[PydanticObjectId] = []
