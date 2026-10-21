"""Lazy public-NOOA bridge; no model runtime is reimplemented here."""

from collections.abc import Awaitable, Callable
from typing import Any


def make_allocator(llm: Any) -> Callable[..., Awaitable[dict[str, dict[str, Any]]]]:
    from nooa import strategy
    from nooa.strategies import CodeActStrategy

    @strategy(CodeActStrategy(), llm=llm)
    async def allocate_members(
        task: Any,
        context: Any,
        member_descriptions: dict[str, str],
        pattern_description: str,
        execution_contract: str,
    ) -> dict[str, dict[str, Any]]:
        """Allocate the team's task and relevant materials to every named member.

        Understand each member's documented capability and the fixed collaboration.
        Return exactly one entry per member name, each containing exactly 'task'
        (its concrete work instructions) and 'context' (only relevant materials).
        Select live objects from the supplied context where appropriate; retain
        their references instead of reconstructing their contents. Do not mutate
        the supplied task/context, execute members, or change the collaboration.

        Members receive their assigned task unchanged. Execution adds a local
        context with 'materials' holding your selected context, 'upstream' holding
        only the direct predecessor's actual result, and 'feedback' holding the
        prior Loop round's final result. Instruct members to use those future
        results when needed; never invent results that have not been produced.
        For multi-step dependencies, instruct the predecessor to carry forward
        required business artifacts. Do not put all available information into
        every allocation or create an execution plan, extra members or retries.
        """
        ...

    return allocate_members
