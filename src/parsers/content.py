from enum import Enum
from io import BytesIO
from typing import Union

import discord
from pypdf import PdfReader
import requests
from result import as_result
import validators
from markdownify import markdownify as md


PLAINTEXT_FORMATS = ["text/markdown", "text/plain", "application/xml"]
IMAGE_FORMATS = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"]


class ContentRetriever:
    ContentType = Enum("ContentType", ["URL", "ATTACHMENT", "TEXT"])

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
            raise ValueError("Invalid content type")
        elif self.content_type == self.ContentType.TEXT and not isinstance(
            self.content, str
        ):
            raise ValueError("Invalid content type")
        elif self.content_type == self.ContentType.URL and not isinstance(
            self.content, str
        ):
            raise ValueError("Invalid content type")

        if self.content_type == self.ContentType.URL and not validators.url(
            self.content
        ):
            raise ValueError("Invalid URL")

    @as_result(Exception)
    async def retrieve(self) -> Union[str, bytes]:
        if self.content_type == self.ContentType.URL:
            if not isinstance(self.content, str):
                raise ValueError("Invalid content type")
            response = requests.get(self.content)
            if response.status_code != 200:
                raise ValueError("Unable to retrieve content")
            if response.headers["Content-Type"] == "text/html":
                return self._handle_html(response.text)
            if response.headers["Content-Type"] == "application/json":
                return response.json()
            if response.headers["Content-Type"] in PLAINTEXT_FORMATS:
                return response.text
            if response.headers["Content-Type"] in IMAGE_FORMATS:
                return response.content
            if response.headers["Content-Type"] == "application/pdf":
                return self._handle_pdf(response.content)
            raise ValueError("Unsupported content type")
        if self.content_type == self.ContentType.TEXT:
            if not isinstance(self.content, str):
                raise ValueError("Invalid content type")
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
            raise ValueError("Unsupported content type")
        raise ValueError("Invalid content type")

    def _handle_html(self, html: str) -> str:
        return md(html)

    def _handle_pdf(self, pdf: bytes) -> str:
        file = BytesIO(pdf)
        reader = PdfReader(file)
        return "\n".join([page.extract_text() for page in reader.pages])
