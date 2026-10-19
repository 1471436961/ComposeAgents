"""Recursive member composition delegated to an explicit Pattern."""

from collections.abc import Mapping, Sequence
from typing import Any

from .members import Members
from .protocols import Pattern, TeamMember


class Team:
    """Hold a nonempty member snapshot and return the Pattern's business result.

    Sequence or mapping inputs become a read-only Members snapshot; changing
    the caller's list or dict does not change this Team. Member objects stay
    live references. A child Team is a member and keeps its own Pattern.
    Patterns declaring requires_named_members reject non-mapping inputs at
    construction. Legacy structural Patterns without the flag default to False.
    Task, context and results are neither copied nor wrapped. Exceptions and
    cancellation propagate without retries or rollback. Callers own member
    resources and state; this container adds no concurrency-safety guarantee.
    The weakly typed TeamMember contract still requires business compatibility.
    """

    def __init__(
        self,
        members: Sequence[TeamMember] | Mapping[str, TeamMember],
        pattern: Pattern,
    ) -> None:
        if getattr(pattern, "requires_named_members", False) and not isinstance(members, Mapping):
            raise ValueError(f"{type(pattern).__name__} requires named members")
        snapshot = Members(members)
        if not snapshot:
            raise ValueError("Team requires at least one member")
        self._members = snapshot
        self.pattern = pattern

    @property
    def members(self) -> Members:
        """The read-only snapshot, containing the original member instances."""
        return self._members

    async def execute(self, task: Any, context: Any) -> Any:
        return await self.pattern.run(self._members, task, context)
