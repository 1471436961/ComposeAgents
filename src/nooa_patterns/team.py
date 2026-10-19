"""Recursive member composition delegated to an explicit Pattern."""

from collections.abc import Sequence
from typing import Any

from .protocols import Pattern, TeamMember


class Team:
    """Hold a nonempty member snapshot and return the Pattern's business result.

    Members are kept by reference in a tuple; changing the caller's list does
    not change this Team. A child Team is a member and keeps its own Pattern.
    Task, context and results are neither copied nor wrapped. Exceptions and
    cancellation propagate without retries or rollback. Callers own member
    resources and state; this container adds no concurrency-safety guarantee.
    The weakly typed TeamMember contract still requires business compatibility.
    """

    def __init__(self, members: Sequence[TeamMember], pattern: Pattern) -> None:
        snapshot = tuple(members)
        if not snapshot:
            raise ValueError("Team requires at least one member")
        self._members = snapshot
        self.pattern = pattern

    @property
    def members(self) -> tuple[TeamMember, ...]:
        """The fixed member sequence, containing the original member instances."""
        return self._members

    async def execute(self, task: Any, context: Any) -> Any:
        return await self.pattern.run(self._members, task, context)
