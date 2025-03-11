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
    Label,
)
from textual.containers import VerticalScroll, VerticalGroup, Vertical
from textual.binding import Binding
from textual import on, events
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

    messages: List[Any]

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
        await self.handler(self.OnReady()) # type: ignore
        self.query_one(Input).focus()

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
        log.write(
            f"[{color}]{record.levelname} [[{time.strftime('%H:%M:%S')}]][/{color}] [white]({record.name})[/white]"
        )
        log.write(f"[light_gray]{record.getMessage()}[/light_gray]")

    @on(Input.Submitted)
    async def input_submitted(self, event: Input.Submitted) -> None:
        input = self.query_one(Input)
        input.clear()
        if event.value == "!q":
            self.exit()
            return
        if len(event.value) == 0:
            return
        if self.handler is not None:
            input.disabled = True
            prev_placeholder = input.placeholder
            input.placeholder = "Thinking..."
            await self.handler(event)
            input.placeholder = prev_placeholder
            input.disabled = False
        input.focus()

    async def on_app_focus(self, event: events.AppFocus) -> None:
        input = self.query_one(Input)
        input.focus()

    def register_handler(self, handler: Callable[[Any], Coroutine[Any, Any, Any]]):
        self.handler = handler

    async def write(self, message: str, role: str = "system"):
        label = {
            "system": "System",
            "bot": "MockBot",
            "user": self.username,
        }
        markdown = Vertical(Label(label.get(role, "System")), Markdown(message.strip()))
        markdown.add_class(role)
        self.messages.append(markdown)
        try:
            chat = self.query_one("#chat_scroll", VerticalScroll)
            await chat.mount(self.messages[-1])
            chat.scroll_page_down()
        except LookupError:
            return
