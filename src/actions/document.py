import json
from typing import ClassVar, List, Optional
from result import Err, Ok, Result
import validators
from actions.action import Action, Context
from mistral import functions
from mistral import rag
from model.document import EmbeddedDocument
from model.project import Project
from parsers.url import url_retrieve
from pydantic.json import pydantic_encoder


class DocumentAdd(Action):
    """
    Add a document to the project.
    """

    urls: List[str]
    project: Optional[str]

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, str]:
        for url in self.urls:
            if not validators.url(url):
                return Err(f"Invalid URL: {url}")
        if self.project:
            for project in ctx.user.projects:
                if project.name == self.project:  # type: ignore
                    self._memo["project"] = project
                    return Ok(None)
        elif ctx.user.default_project is not None:
            self._memo["project"] = ctx.user.default_project
            return Ok(None)
        return Err("Project not found")

    def preflight_wrap(self, result: Result[None, str]) -> Result[None, str]:
        return result

    async def execute(self, ctx: Context) -> Result[None, Exception]:
        project = self._memo["project"]
        for url in self.urls:
            try:
                content = " ".join(await url_retrieve(url))
                title = functions.title_document(content).unwrap_or("Untitled")
                document = rag.Document(title=title, text=content)
                doc_ids = await rag.embed_document(document, project)

                embedded_doc = EmbeddedDocument(
                    title=title,
                    project=project.id,
                    document_ids=doc_ids,
                )

                await embedded_doc.save()
                project.documents.append(embedded_doc)
                await project.save()
            except Exception as e:
                return Err(e)
        return Ok(None)

    def execute_wrap(self, result: Result[None, Exception]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Error adding document: {result.unwrap_err()}")
        return Ok("Document added successfully")

    def __str__(self) -> str:
        return f"Add documents to {self.project} ({', '.join(self.urls)})"


class DocumentRemove(Action):
    """
    Remove a document from the project.
    """

    name: str
    project: Optional[str]

    effective: ClassVar[bool] = True
    unsafe: ClassVar[bool] = True

    async def preflight(self, ctx: Context) -> Result[None, str]:
        project: Optional[Project] = None
        if self.project:
            for p in ctx.user.projects:
                if p.name == self.project:  # type: ignore
                    project = p  # type: ignore
                    break
        elif ctx.user.default_project is not None:
            p = ctx.user.default_project
        if project is None:
            return Err("Project not found")
        self._memo["project"] = project
        for document in project.documents:
            if document.title == self.name:
                self._memo["document"] = document
                return Ok(None)
        return Err("Document not found")

    def preflight_wrap(self, result: Result[None, str]) -> Result[None, str]:
        return result

    async def execute(self, ctx: Context) -> Result[None, Exception]:
        project = self._memo["project"]
        document = self._memo["document"]
        try:
            await rag.delete_documents(document.document_ids)
            await document.delete()
            project.documents.remove(document)
            await project.save()
        except Exception as e:
            return Err(e)
        return Ok(None)

    def execute_wrap(self, result: Result[None, Exception]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Error removing document: {result.unwrap_err()}")
        return Ok("Document removed successfully")

    def __str__(self) -> str:
        return f"Remove document {self.name} from {self.project}"


class DocumentList(Action):
    """
    List documents in the project.
    """

    project: Optional[str]

    effective: ClassVar[bool] = False
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, str]:
        if self.project:
            for project in ctx.user.projects:
                if project.name == self.project:  # type: ignore
                    self._memo["project"] = project
                    return Ok(None)
        elif ctx.user.default_project is not None:
            self._memo["project"] = ctx.user.default_project
            return Ok(None)
        return Err("Project not found")

    def preflight_wrap(self, result: Result[None, str]) -> Result[None, str]:
        return result

    async def execute(self, ctx: Context) -> Result[str, Exception]:
        project = self._memo["project"]
        if len(project.documents) == 0:
            return Ok("No documents found")
        return Ok(
            "**Documents:**\n"
            + "\n".join(
                f"{i + 1}. {doc.title}" for i, doc in enumerate(project.documents)
            )
        )

    def execute_wrap(self, result: Result[str, Exception]) -> Result[str, str]:
        if result.is_err():
            return Err(f"Error listing documents: {result.unwrap_err()}")
        return Ok(result.unwrap())

    def __str__(self) -> str:
        return f"List documents in {self.project}"


class DocumentSearch(Action):
    """
    Search for documents in the project.
    """

    query: str
    project: Optional[str]
    limit: Optional[int]

    effective: ClassVar[bool] = False
    unsafe: ClassVar[bool] = False

    async def preflight(self, ctx: Context) -> Result[None, str]:
        if self.project:
            for project in ctx.user.projects:
                if project.name == self.project:  # type: ignore
                    self._memo["project"] = project
                    return Ok(None)
        elif ctx.user.default_project is not None:
            self._memo["project"] = ctx.user.default_project
            return Ok(None)
        return Err("Project not found")

    def preflight_wrap(self, result: Result[None, str]) -> Result[None, str]:
        return result

    async def execute(
        self, ctx: Context
    ) -> Result[List[rag.QueriedDocument], Exception]:
        project = self._memo["project"]
        return await rag.query_documents(self.query, project.id, self.limit)

    def execute_wrap(
        self, result: Result[List[rag.QueriedDocument], Exception]
    ) -> Result[str, str]:
        if result.is_err():
            return Err(f"Error searching documents: {result.unwrap_err()}")
        return Ok(json.dumps(result.unwrap(), default=pydantic_encoder))

    def __str__(self) -> str:
        return f"Search for documents in {self.project}"
