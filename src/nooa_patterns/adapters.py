"""Explicit callable bridges to the weakly typed member protocol."""

from collections.abc import Awaitable, Callable
from typing import Any

from .protocols import TeamMember


class _CallableMember:
    """Keep the original callable and expose a real async execute method."""

    def __init__(self, fn: Callable[[Any, Any], Awaitable[Any]]) -> None:
        self._fn = fn

    async def execute(self, task: Any, context: Any) -> Any:
        return await self._fn(task, context)


def as_member(fn: Callable[[Any, Any], Awaitable[Any]]) -> TeamMember:
    """Wrap an explicit (task, context) callable without inferring semantics.

    The callable must return an awaitable. Task, context, results and callable
    state remain live references; exceptions and cancellation propagate.
    Adapt other signatures with an explicit async bridge before calling this
    function. No signature inspection, context injection or copying occurs.

    This weakly typed bridge adds no NOOA validation contract. Calling a NOOA
    public method through the bridge still uses that method's native checks.
    """
    return _CallableMember(fn)
