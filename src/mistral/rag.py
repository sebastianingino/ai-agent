from typing import Any, List, Mapping, Optional, Sequence
from beanie import PydanticObjectId
from mistralai import SystemMessage, UserMessage
from pydantic import BaseModel
from result import Err, Ok, Result
from database import database
from mistral.chat import ERROR_RESPONSE, MISTRAL_MODEL, SYSTEM_PROMPT, Chat
from model.project import Project

CHUNK_SIZE = 2048
MODEL = "mistral-embed"
DEFAULT_LIMIT = 5


class Document(BaseModel):
    title: str
    text: str


class EmbeddedDocument(BaseModel):
    title: str
    text: str
    embedding: List[float]

    project: PydanticObjectId


class QueriedDocument(BaseModel):
    title: str
    text: str
    project: PydanticObjectId

    def rag_string(self) -> str:
        return f"### {self.title} \n{self.text}"


def rag_chunk(text: str) -> List[str]:
    """Split the text into chunks of 2048 characters."""
    return [text[i : i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]


async def generate_embedding(input_text: str) -> Result[List[float], Exception]:
    """Generate embeddings for the input texts."""
    try:
        response = await Chat.client.embeddings.create_async(
            model=MODEL,
            inputs=input_text,
        )
        if response and response.data[0].embedding:
            return Ok(response.data[0].embedding)
        return Err(ValueError("No embeddings found"))
    except Exception as e:
        return Err(e)


async def embed_document(
    document: Document, project: Project
) -> List[PydanticObjectId]:
    if not project.id:
        raise ValueError("Project ID not found")

    if database.rag_collection is None:
        raise ValueError("MongoDB collection not found")

    embeddings = []
    for chunk in rag_chunk(document.text):
        embedding = await generate_embedding(chunk)
        if embedding.is_err():
            continue
        embeddings.append(
            EmbeddedDocument(
                title=document.title,
                text=chunk,
                embedding=embedding.unwrap(),
                project=project.id,
            )
        )

    result = await database.rag_collection.insert_many(
        [doc.dict() for doc in embeddings]
    )
    return result.inserted_ids


async def query_documents(
    query: str, project_id: PydanticObjectId, limit: Optional[int]
) -> Result[List[QueriedDocument], Exception]:
    if database.rag_collection is None:
        raise ValueError("MongoDB collection not found")

    embedded_query = await generate_embedding(query)
    if embedded_query.is_err():
        return Err(embedded_query.unwrap_err())

    pipeline: Sequence[Mapping[str, Any]] = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "queryVector": embedded_query.unwrap(),
                "path": "embedding",
                "exact": True,
                "limit": limit or DEFAULT_LIMIT,
                "filter": {"project": project_id},
            }
        },
        {
            "$project": {
                "_id": 0,
                "title": 1,
                "text": 1,
                "project": 1,
            }
        },
    ]

    try:
        results = await database.rag_collection.aggregate(pipeline).to_list(5)
        return Ok([QueriedDocument(**result) for result in results])
    except Exception as e:
        return Err(e)


async def query_all_documents(
    query: str, projects: List[PydanticObjectId], limit: Optional[int]
) -> Result[List[QueriedDocument], Exception]:
    if database.rag_collection is None:
        raise ValueError("MongoDB collection not found")
    if len(projects) == 0:
        raise ValueError("No projects found")

    embedded_query = await generate_embedding(query)
    if embedded_query.is_err():
        return Err(embedded_query.unwrap_err())

    pipeline: Sequence[Mapping[str, Any]] = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "queryVector": embedded_query.unwrap(),
                "path": "embedding",
                "exact": True,
                "limit": limit or DEFAULT_LIMIT,
                "filter": {"project": {"$in": projects}},
            }
        },
        {
            "$project": {
                "_id": 0,
                "title": 1,
                "text": 1,
                "project": 1,
            }
        },
    ]

    try:
        results = await database.rag_collection.aggregate(pipeline).to_list(5)
        return Ok([QueriedDocument(**result) for result in results])
    except Exception as e:
        return Err(e)


async def delete_documents(document_ids: List[PydanticObjectId]) -> None:
    if database.rag_collection is None:
        raise ValueError("MongoDB collection not found")

    await database.rag_collection.delete_many({"_id": {"$in": document_ids}})


async def respond(query: str, documents: List[QueriedDocument]):
    context = f"""
The user is searching for the query. The following documents have been found are relevant to this query:
---
{"\n\n".join(document.rag_string() for document in documents)}
---
Given the context and not prior knowledge, answer the query. Please keep your answer concise and informative. Cite the relevant documents if necessary by referring to the document name and section.
        """.strip()

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=context),
        UserMessage(content=f"Query: {query}\n Answer:"),
    ]

    response = await Chat.client.chat.complete_async(
        model=MISTRAL_MODEL,
        messages=messages,  # type: ignore
    )

    if response.choices and response.choices[0].message.content:
        return str(response.choices[0].message.content)

    return ERROR_RESPONSE
