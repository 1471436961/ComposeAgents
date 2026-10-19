"""Concurrent member calls with ordered results and cancellation cleanup."""

import asyncio
from collections.abc import Sequence
from typing import Any

from ..protocols import TeamMember


class Parallel:
    """Call all members with the same live inputs and collect an ordered list.

    The result list follows member order, not completion order. Each element
    keeps its original identity, including None and nested lists; one member
    still produces a one-element list. Team rejects empty members at
    construction; direct run calls also reject an empty sequence.

    On the first observed failure, cancel unfinished siblings and wait for all
    owned tasks before propagating the original exception, without grouping,
    retries, partial results or rollback. A member's cancellation also aborts
    collection. Outer cancellation requests cancellation of every unfinished
    member and waits for their completion. Cleanup errors do not replace the
    triggering business exception; another outer cancellation can still win.

    Cancellation is cooperative: cleanup or a member that suppresses it may
    delay propagation. No timeout is built in and independently spawned
    background tasks are not owned by this Pattern. Callers own resources and
    concurrent access to task, context and member instances. Neither input is
    copied, locked, injected into or persisted. Every run owns its task list
    locally, so the Pattern has no execution state and can be reused.
    """

    async def run(
        self,
        members: Sequence[TeamMember],
        task: Any,
        context: Any,
    ) -> list[Any]:
        if not members:
            raise ValueError("Parallel requires at least one member")

        async def execute(member: TeamMember) -> Any:
            return await member.execute(task, context)

        pending = [asyncio.create_task(execute(member)) for member in members]
        collected = asyncio.gather(*pending)
        try:
            # Forward outer cancellation explicitly so cleanup errors cannot
            # replace the caller's CancelledError in the collector.
            return await asyncio.shield(collected)
        except BaseException:
            for child in pending:
                if not child.done():
                    child.cancel()
            await asyncio.gather(collected, *pending, return_exceptions=True)
            raise
