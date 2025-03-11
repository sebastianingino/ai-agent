import logging
import re
import discord
import requests
import validators
from enum import Enum
from typing import List, TypedDict, Union
from result import Err, Ok, Result
from markdownify import markdownify as md  # type: ignore
from mistral.ocr import URL_TYPE, ocr
from parsers.formats import IMAGE_FORMATS, PLAINTEXT_FORMATS
from parsers.mime import MimeType


LOGGER = logging.getLogger(__name__)


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

    async def retrieve(self) -> List[str]:
        if self.content_type == self.ContentType.URL:
            if not isinstance(self.content, str):
                raise ValueError("Invalid content type")
            response = requests.head(self.content)
            if response.status_code != 200:
                raise ValueError("Unable to retrieve content")
            mimeType = MimeType.from_content_type(response.headers["Content-Type"])
            if mimeType.type == "text/html":
                return [md(requests.get(self.content).text)]
            if mimeType.type in PLAINTEXT_FORMATS:
                return [response.text]
            if mimeType.type in IMAGE_FORMATS:
                return await ocr(self.content, URL_TYPE.IMAGE)
            if mimeType.type == "application/pdf":
                return await ocr(self.content, URL_TYPE.DOCUMENT)
            raise ValueError(
                f"Unsupported content type: {response.headers['Content-Type']}"
            )
        if self.content_type == self.ContentType.TEXT:
            if not isinstance(self.content, str):
                raise ValueError(f"Invalid content type: {type(self.content)}")
            return [self.content]
        if self.content_type == self.ContentType.ATTACHMENT:
            if not isinstance(self.content, discord.Attachment):
                raise ValueError("Invalid content type")
            if self.content.content_type in PLAINTEXT_FORMATS:
                return [(await self.content.read()).decode("utf-8")]
            if self.content.content_type in IMAGE_FORMATS:
                return await ocr(self.content.url, URL_TYPE.IMAGE)
            if self.content.content_type == "text/html":
                return [md((await self.content.read()).decode("utf-8"))]
            if self.content.content_type == "application/pdf":
                return await ocr(self.content.url, URL_TYPE.DOCUMENT)
            raise ValueError(f"Unsupported content type: {self.content.content_type}")
        raise ValueError("Invalid content type")


Content = TypedDict(
    "Content",
    {"content": str, "attachments": List[str]},
)


async def from_message(
    message: discord.Message, content: str
) -> Result[Content, Exception]:
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

        attachments: List[str] = []
        for retriever in url_retrievers + attachment_retrievers:
            retrieval = await retriever.retrieve()
            attachments += retrieval

        result: Content = {
            "content": content_without_urls,
            "attachments": attachments,
        }
        return Ok(result)
    except Exception as e:
        return Err(e)
