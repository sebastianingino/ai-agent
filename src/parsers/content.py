from dataclasses import dataclass
from enum import Enum
from io import BytesIO
import re
from typing import Dict, List, TypedDict, Union

import discord
from pypdf import PdfReader
import requests
from result import Err, Ok, Result
import validators
from markdownify import markdownify as md


PLAINTEXT_FORMATS = ["text/markdown", "text/plain", "application/xml"]
IMAGE_FORMATS = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"]


class ContentRetriever:
    ContentType = Enum("ContentType", ["URL", "ATTACHMENT", "TEXT"])

    @dataclass
    class MimeType:
        type: str
        parameters: Dict[str, str]

    content_type: ContentType
    content: Union[str, discord.Attachment]

    def __init__(
        self, content_type: ContentType, content: Union[str, discord.Attachment]
    ):
        self.content_type = content_type
        self.content = content

        if self.content_type == self.ContentType.ATTACHMENT and not isinstance(
            self.content, discord.Attachment
        ):
            raise ValueError(f"Invalid content type: {type(self.content)}")
        elif self.content_type == self.ContentType.TEXT and not isinstance(
            self.content, str
        ):
            raise ValueError(f"Invalid content type: {type(self.content)}")
        elif self.content_type == self.ContentType.URL and not isinstance(
            self.content, str
        ):
            raise ValueError(f"Invalid content type: {type(self.content)}")

        if self.content_type == self.ContentType.URL and not validators.url(
            self.content
        ):
            raise ValueError(f"Invalid URL: {self.content}")

    async def retrieve(self) -> Union[str, bytes]:
        if self.content_type == self.ContentType.URL:
            if not isinstance(self.content, str):
                raise ValueError("Invalid content type")
            response = requests.get(self.content)
            if response.status_code != 200:
                raise ValueError("Unable to retrieve content")
            mimeType = self._to_mime_type(response.headers["Content-Type"])
            if mimeType.type == "text/html":
                return self._handle_html(response.text)
            if mimeType.type == "application/json":
                return response.json()
            if mimeType.type in PLAINTEXT_FORMATS:
                return response.text
            if mimeType.type in IMAGE_FORMATS:
                return response.content
            if mimeType.type == "application/pdf":
                return self._handle_pdf(response.content)
            raise ValueError(
                f"Unsupported content type: {response.headers['Content-Type']}"
            )
        if self.content_type == self.ContentType.TEXT:
            if not isinstance(self.content, str):
                raise ValueError(f"Invalid content type: {type(self.content)}")
            return self.content
        if self.content_type == self.ContentType.ATTACHMENT:
            if not isinstance(self.content, discord.Attachment):
                raise ValueError("Invalid content type")
            if self.content.content_type in PLAINTEXT_FORMATS:
                return (await self.content.read()).decode("utf-8")
            if self.content.content_type in IMAGE_FORMATS:
                return await self.content.read()
            if self.content.content_type == "text/html":
                return self._handle_html((await self.content.read()).decode("utf-8"))
            if self.content.content_type == "application/pdf":
                return self._handle_pdf(await self.content.read())
            raise ValueError(f"Unsupported content type: {self.content.content_type}")
        raise ValueError("Invalid content type")

    def _handle_html(self, html: str) -> str:
        return md(html)

    def _handle_pdf(self, pdf: bytes) -> str:
        file = BytesIO(pdf)
        reader = PdfReader(file)
        return "\n".join([page.extract_text() for page in reader.pages])

    def _to_mime_type(self, content_type: str) -> MimeType:
        parts = content_type.split(";")
        return self.MimeType(parts[0], dict(part.split("=") for part in parts[1:]))


Content = TypedDict(
    "Content",
    {"content": str, "text_attachments": List[str], "image_attachments": List[bytes]},
)


async def from_message(message: discord.Message, content: str) -> Result[Content, Exception]:
    try:
        urls = re.findall(r"(https?://\S+)", content)
        urls.extend((embed.url for embed in message.embeds if embed.url))
        content_without_urls = re.sub(r"(https?://\S+)", "", content)
        url_retrievers = [
            ContentRetriever(ContentRetriever.ContentType.URL, url) for url in set(urls)
        ]
        attachment_retrievers = [
            ContentRetriever(ContentRetriever.ContentType.ATTACHMENT, attachment)
            for attachment in message.attachments
        ]

        text_attachments: List[str] = []
        image_attachments: List[bytes] = []
        for retriever in url_retrievers + attachment_retrievers:
            retrieval = await retriever.retrieve()
            if isinstance(retrieval, str):
                text_attachments.append(retrieval)
            elif isinstance(retrieval, bytes):
                image_attachments.append(retrieval)
            else:
                raise ValueError(f"Unsupported content type: {type(retrieval)}")

        result: Content = {
            "content": content_without_urls,
            "text_attachments": text_attachments,
            "image_attachments": image_attachments,
        }
        return Ok(result)
    except Exception as e:
        return Err(e)
