from enum import Enum
from typing import List, Union
from mistral.chat import Chat
from mistralai import DocumentURLChunk, ImageURLChunk

MODEL = "mistral-ocr-latest"

URL_TYPE = Enum("URL_TYPE", ["DOCUMENT", "IMAGE"])


async def ocr(url: str, url_type: URL_TYPE) -> List[str]:
    document: Union[DocumentURLChunk, ImageURLChunk]
    if url_type == URL_TYPE.DOCUMENT:
        document = DocumentURLChunk(document_url=url)
    elif url_type == URL_TYPE.IMAGE:
        document = ImageURLChunk(image_url=url)
    else:
        raise ValueError("Invalid URL type")
    ocr_response = await Chat.client.ocr.process_async(
        model=MODEL,
        document=document,
    )

    pages = []
    for page in ocr_response.pages:
        pages.append(page.markdown)

    return pages
