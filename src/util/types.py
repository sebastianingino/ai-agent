from typing import Any, Callable, Coroutine


AsyncCallable = Callable[..., Coroutine[Any, Any, Any]]
