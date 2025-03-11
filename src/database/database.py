import asyncio
import logging
from typing import List, Type
from beanie import Document, init_beanie
from mistralai import Optional
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from pymongo import IndexModel
from pymongo.server_api import ServerApi
from pymongo.operations import SearchIndexModel

ENDPOINT = "mongodb+srv://admin:admin@kubot.a4flu.mongodb.net/?retryWrites=true&w=majority&appName=kubot"
LOGGER = logging.getLogger(__name__)
TIMEOUT = 120
EMBEDDING_SIZE = 1024

rag_collection: Optional[AsyncIOMotorCollection] = None
RAG_COLLECTION_NAME = "RAG"
RAG_INDEX_NAME = "vector_index"
PROJECT_ID_INDEX_NAME = "project_id_index"


async def init_database(models: List[Type[Document]]):
    logging.getLogger("pymongo").setLevel(logging.INFO)
    client: AsyncIOMotorClient = AsyncIOMotorClient(ENDPOINT, server_api=ServerApi("1"))

    await init_beanie(
        database=client.kubot,
        document_models=models,
    )

    await init_rag_database(client.kubot)


async def init_rag_database(db: AsyncIOMotorDatabase):
    global rag_collection
    if (await db.list_collection_names()).count(RAG_COLLECTION_NAME) == 0:
        rag_collection = await db.create_collection(RAG_COLLECTION_NAME)
    else:
        rag_collection = db.get_collection("RAG")

    indices = await rag_collection.list_indexes().to_list()
    if not any(index["name"] == PROJECT_ID_INDEX_NAME for index in indices):
        await create_project_index(rag_collection)

    search_indices = await rag_collection.list_search_indexes(RAG_INDEX_NAME).to_list()
    if not any(index["name"] == RAG_INDEX_NAME for index in search_indices):
        await create_rag_index(rag_collection)


async def create_project_index(collection: AsyncIOMotorCollection):
    project_id_index = IndexModel([("project", 1)], name=PROJECT_ID_INDEX_NAME)
    await collection.create_indexes([project_id_index])

    LOGGER.info("Awaiting index creation")
    for _ in range(TIMEOUT // 5):
        indices = await collection.list_indexes().to_list()
        if any(index["name"] == PROJECT_ID_INDEX_NAME for index in indices):
            break
        await asyncio.sleep(5)
    else:
        raise ValueError("Index creation failed")


async def create_rag_index(collection: AsyncIOMotorCollection):
    search_index_model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "numDimensions": EMBEDDING_SIZE,
                    "path": "embedding",
                    "similarity": "cosine",
                },
                {
                    "type": "filter",
                    "path": "project",
                },
            ]
        },
        name=RAG_INDEX_NAME,
        type="vectorSearch",
    )
    await collection.create_search_index(search_index_model)

    LOGGER.info("Awaiting RAG index creation")
    for _ in range(TIMEOUT // 5):
        indices = await collection.list_search_indexes(RAG_INDEX_NAME).to_list()
        if any(index["name"] == RAG_INDEX_NAME for index in indices):
            break
        await asyncio.sleep(5)
    else:
        raise ValueError("RAG index creation failed")

    LOGGER.info("Rag index created")
