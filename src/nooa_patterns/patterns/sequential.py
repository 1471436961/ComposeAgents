"""Sequential result handoff using ordinary async calls."""

from collections.abc import Sequence
from typing import Any

from ..protocols import TeamMember


class Sequential:
    """Pass each business result to the next member without execution state.

    The first member receives the entry task; all receive the same context.
    Inputs, context and results stay live references. None is an ordinary
    result. Exceptions and cancellation propagate without retry or rollback.
    No execution progress is saved on this instance or in shared storage, so
    it can be reused. This does not make members or context concurrency-safe.

    members must be nonempty: this is a caller precondition. Empty sequences
    are unsupported and their behavior is not guaranteed. Team will enforce
    the precondition at construction in M3. Business compatibility remains
    the caller's responsibility under the weakly typed TeamMember protocol.
    """

    async def run(
        self,
        members: Sequence[TeamMember],
        task: Any,
        context: Any,
    ) -> Any:
        current = task
        for member in members:
            current = await member.execute(current, context)
        return current
