import logging
import sys
import time
from textual.app import App, ComposeResult
from textual.widgets import (
    Footer,
    Header,
    Placeholder,
    TabbedContent,
    TabPane,
    Markdown,
    Input,
    RichLog,
)
from textual.containers import VerticalScroll, VerticalGroup
from textual.binding import Binding
from textual import on
from typing import Any, Callable, Coroutine, List, Optional
from textual._context import active_app


class CustomHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        """Invoked by logging."""
        message = self.format(record)
        try:
            app = active_app.get()
        except LookupError:
            print(message, file=sys.stderr)
        else:
            app.write_log(record)  # type: ignore


logging.root.addHandler(CustomHandler())
logging.root.setLevel(logging.DEBUG)

class MockBotUI(App):
    CSS_PATH = "mockbot_ui.tcss"

    InputSubmitted = Input.Submitted

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "clear", "Clear"),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    messages: List[Markdown]

    handler: Optional[Callable[[Any], Coroutine[Any, Any, Any]]]

    username: str = "Mock User"

    def __init__(self):
        super().__init__()
        self.messages = []
        self.handler = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(name="MockBot UI")
        yield Footer()
        with TabbedContent(initial="chat"):
            with TabPane("Chat", id="chat"):
                with VerticalGroup():
                    yield VerticalScroll(id="chat_scroll")
                    yield Input(placeholder="Type here...", id="input")
            with TabPane("Logs", id="logs"):
                yield RichLog(markup=True, wrap=True)
            with TabPane("Settings", id="settings"):
                yield Placeholder()

    async def on_ready(self):
        """Called when the app is ready."""
        chat = self.query_one("#chat_scroll", VerticalScroll)
        if len(self.messages) > 0:
            chat.mount(self.messages[-1])
        await self.handler(self.OnReady())

    class OnReady:
        pass

    def write_log(self, record: logging.LogRecord) -> None:
        log = self.query_one(RichLog)
        colors = {
            logging.DEBUG: "blue",
            logging.INFO: "green",
            logging.WARNING: "yellow",
            logging.ERROR: "red",
            logging.CRITICAL: "red",
        }
        color = colors.get(record.levelno, "white")
        log.write(f"[{color}]{record.levelname} [[{time.strftime('%H:%M:%S')}]][/{color}] [white]({record.name})[/white]")
        log.write(f"[light_gray]{record.getMessage()}[/light_gray]")

    @on(Input.Submitted)
    async def input_submitted(self, event: Input.Submitted) -> None:
        if event.value == "!q":
            self.exit()
            return
        if len(event.value) == 0:
            return
        if self.handler is not None:
            await self.handler(event)
        self.query_one(Input).clear()

    def register_handler(self, handler: Callable[[Any], Coroutine[Any, Any, Any]]):
        self.handler = handler

    def write(self, message: str):
        markdown = Markdown(message.strip())
        self.messages.append(markdown)
        try:
            chat = self.query_one("#chat_scroll", VerticalScroll)
            chat.mount(self.messages[-1])
            chat.scroll_end()
        except LookupError:
            return
