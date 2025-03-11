import requests
from typing import List
from mistral.ocr import URL_TYPE, ocr
from parsers.formats import IMAGE_FORMATS, PLAINTEXT_FORMATS
from parsers.mime import MimeType
from markdownify import markdownify as md  # type: ignore


async def url_retrieve(url: str) -> List[str]:
    response = requests.head(url)
    if response.status_code != 200:
        raise ValueError("Unable to retrieve content")
    mimeType = MimeType.from_content_type(response.headers["Content-Type"])
    if mimeType.type == "text/html":
        return [md(requests.get(url).text)]
    if mimeType.type in PLAINTEXT_FORMATS:
        return [response.text]
    if mimeType.type in IMAGE_FORMATS:
        return await ocr(url, URL_TYPE.IMAGE)
    if mimeType.type == "application/pdf":
        return await ocr(url, URL_TYPE.DOCUMENT)
    raise ValueError(f"Unsupported content type: {response.headers['Content-Type']}")
