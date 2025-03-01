import logging
from typing import List, Type
from beanie import Document, init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi

ENDPOINT = "mongodb+srv://admin:admin@kubot.a4flu.mongodb.net/?retryWrites=true&w=majority&appName=kubot"

async def init_database(models: List[Type[Document]]):
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    client = AsyncIOMotorClient(ENDPOINT, server_api=ServerApi("1"))

    await init_beanie(
        database=client.db_name,
        document_models=models,
    )
