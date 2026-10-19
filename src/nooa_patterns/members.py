"""Ordered member snapshots with optional explicit names."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .protocols import TeamMember


class Members:
    """Snapshot a sequence or string-keyed mapping without copying members.

    Iteration always yields member objects, in sequence or mapping order.
    Integer access follows tuple indexing, including negative indices; string
    access uses explicit names and raises KeyError if absent. names is a
    read-only tuple in mapping order. No names are invented for a sequence.
    Empty snapshots are allowed here; Team rejects them at construction.
    This container has no public mutation API and does not reset member state.
    """

    def __init__(
        self, members: Sequence[TeamMember] | Mapping[str, TeamMember]
    ) -> None:
        self._named = dict(members) if isinstance(members, Mapping) else {}
        if any(not isinstance(name, str) for name in self._named):
            raise TypeError("Member names must be strings")
        self._ordered = (
            tuple(self._named.values()) if isinstance(members, Mapping) else tuple(members)
        )
        self._names = tuple(self._named)

    def __iter__(self) -> Iterator[TeamMember]:
        return iter(self._ordered)

    def __len__(self) -> int:
        return len(self._ordered)

    def __getitem__(self, key: int | str) -> TeamMember:
        if isinstance(key, str):
            return self._named[key]
        if isinstance(key, int):
            return self._ordered[key]
        raise TypeError("Member index must be an int or str")

    @property
    def names(self) -> tuple[str, ...]:
        """Explicit names in snapshot order, or an empty tuple for a sequence."""
        return self._names

    def has_name(self, name: str) -> bool:
        return name in self._named
