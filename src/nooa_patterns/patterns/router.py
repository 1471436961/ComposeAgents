"""A synchronous business decision selects exactly one named member."""

from collections.abc import Callable
from typing import Any, ClassVar

from ..members import Members


class Router:
    """Select one name and return that member's unwrapped business result.

    selector 应是纯函数式的同步决策，不应调用 LLM 或做 I/O；
    模型决策应由前置异步成员完成，selector 只读其产物。

    Team checks the named-member requirement at construction. Direct run
    calls also require nonempty named Members. Each execution calls selector
    once with the original task and context, then awaits only the selected
    member with those same references. None is an ordinary return value.

    Non-string selections raise TypeError; unknown names raise LookupError
    listing available names in snapshot order. Selector and member errors,
    including cancellation, propagate without wrapping, retries or rollback.
    No context fields are injected and member resources remain caller-owned.
    The selector is fixed configuration; names and results stay local to run.
    """

    requires_named_members: ClassVar[bool] = True

    def __init__(self, selector: Callable[[Any, Any], str]) -> None:
        self.selector = selector

    async def run(self, members: Members, task: Any, context: Any) -> Any:
        if not members.names:
            raise ValueError("Router requires named members")
        name = self.selector(task, context)
        if not isinstance(name, str):
            raise TypeError("selector must return a member name as str")
        if not members.has_name(name):
            raise LookupError(f"selector returned {name!r}, available: {list(members.names)!r}")
        return await members[name].execute(task, context)
