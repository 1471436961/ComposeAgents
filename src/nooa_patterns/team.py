"""Recursive teams with one semantic allocation and deterministic execution."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

from .adapters import _CallableMember
from .pattern_kind import PatternKind
from .protocols import TeamMember


class AllocationError(Exception):
    """An allocation failure; team identifies its origin and __cause__ explains it."""

    def __init__(self, message: str, *, team: Team) -> None:
        super().__init__(message)
        self.team = team


class Team:
    """Allocate named work, execute a fixed collaboration, return business results.

    Members may be NOOA-backed leaves or nested Teams. The constructor takes a
    shallow snapshot of a nonempty dict (one member is valid); members and
    pattern are read-only, while member objects remain live and stateful.
    Each execute calls allocate once; nested execute calls allocate independently.
    Sequential/Loop keep assigned tasks and deliver actual results via local
    context. Parallel collects a named dict; Router returns the selected result.

    The complete weakly typed execution contract is also documented on
    TeamMember. It does not validate business compatibility or confer NOOA's
    type contracts; native NOOA method validation still applies when called.
    Callers own clients, resources, shared state, timeouts and concurrency safety.
    """

    def __init__(
        self,
        members: dict[str, TeamMember],
        pattern: PatternKind,
        *,
        llm: Any,
        selector: Callable[[Any, Any], str] | None = None,
        until: Callable[[Any, Any], bool] | None = None,
        max_iterations: int | None = None,
    ) -> None:
        if not isinstance(members, dict):
            raise TypeError("members must be a dict of named members")
        if not members:
            raise ValueError("Team requires at least one member")
        if any(not isinstance(name, str) for name in members):
            raise TypeError("member names must be strings")
        if not isinstance(pattern, PatternKind):
            raise TypeError("pattern must be a PatternKind")
        if pattern is PatternKind.ROUTER:
            self._require_sync(selector, "selector")
        elif selector is not None:
            raise ValueError("selector is only valid for ROUTER")
        if pattern is PatternKind.LOOP:
            self._require_sync(until, "until")
            if isinstance(max_iterations, bool) or not isinstance(max_iterations, int):
                raise TypeError("LOOP requires an integer max_iterations, not bool")
            if max_iterations <= 0:
                raise ValueError("max_iterations must be positive")
        elif until is not None or max_iterations is not None:
            raise ValueError("until and max_iterations are only valid for LOOP")
        self._members = MappingProxyType(dict(members))
        self._pattern = pattern
        self._llm = llm
        self._selector = selector
        self._until = until
        self._max_iterations = max_iterations

    @staticmethod
    def _require_sync(fn: Any, name: str) -> None:
        if not callable(fn) or inspect.iscoroutinefunction(fn) or inspect.iscoroutinefunction(
            getattr(fn, "__call__", None)
        ):
            raise TypeError(f"{name} must be a synchronous callable")

    @property
    def members(self) -> Mapping[str, TeamMember]:
        """The read-only named snapshot; member identities are preserved."""
        return self._members

    @property
    def pattern(self) -> PatternKind:
        """The collaboration chosen at construction."""
        return self._pattern

    def _describe_members(self) -> dict[str, str]:
        from nooa.agentdoc import doc

        descriptions = {}
        for name, member in self._members.items():
            if isinstance(member, _CallableMember):
                source = member._fn
                owner = getattr(source, "__self__", None)
                descriptions[name] = doc(type(owner), source) if owner is not None else doc(source)
            else:
                descriptions[name] = doc(type(member), member.execute)
                if isinstance(member, Team):
                    descriptions[name] += "\nCollaboration: " + member._describe_pattern()
        return descriptions

    def _describe_pattern(self) -> str:
        descriptions = {
            PatternKind.SEQUENTIAL: (
                "Run in member order; only the direct predecessor is in upstream; "
                "return the last result."
            ),
            PatternKind.PARALLEL: (
                "Run independently and concurrently; upstream is empty; "
                "return a dict of named results."
            ),
            PatternKind.ROUTER: (
                "A synchronous selector chooses one named member; "
                "return only that member's result."
            ),
            PatternKind.LOOP: (
                "Repeat a full sequential round; prior round's final result is feedback; "
                "return the final result."
            ),
        }
        text = f"{self._pattern.value}: {descriptions[self._pattern]}"
        if self._pattern is PatternKind.LOOP:
            text += (
                f" max_iterations={self._max_iterations}; "
                f"until: {inspect.getdoc(self._until) or 'caller supplied'}"
            )
        if self._pattern is PatternKind.ROUTER:
            text += f" selector: {inspect.getdoc(self._selector) or 'caller supplied'}"
        return text

    def _describe_execution(self) -> str:
        from nooa.agentdoc import doc

        return doc(type(self), self.execute)

    async def _generate_assignments(self, **inputs: Any) -> dict[str, dict[str, Any]]:
        from ._allocation import make_allocator

        return await make_allocator(self._llm)(**inputs)

    def _validate_assignments(self, assignments: Any) -> None:
        if not isinstance(assignments, dict):
            raise TypeError("allocation must be a dict")
        if assignments.keys() != self._members.keys():
            raise ValueError(f"allocation names must match {list(self._members)!r}")
        for name, assignment in assignments.items():
            if not isinstance(assignment, dict):
                raise TypeError(f"allocation for {name!r} must be a dict")
            if assignment.keys() != {"task", "context"}:
                raise ValueError(f"allocation for {name!r} requires exactly task and context")

    async def allocate(self, task: Any, context: Any) -> dict[str, dict[str, Any]]:
        """Describe and allocate once, validate, return without executing members.

        Quality depends on clear member class/method docstrings and annotations
        describing capabilities, accepted inputs and business results. A preview
        costs a generation; a later execute allocates independently. Ordinary
        allocation errors retain their cause in AllocationError; cancellation and
        other BaseExceptions propagate. No workflow retry or fallback occurs.
        Native NOOA generation may itself use multiple model turns or retries.
        """
        try:
            assignments = await self._generate_assignments(
                task=task,
                context=context,
                member_descriptions=self._describe_members(),
                pattern_description=self._describe_pattern(),
                execution_contract=self._describe_execution(),
            )
            self._validate_assignments(assignments)
            return assignments
        except Exception as exc:
            raise AllocationError("Team allocation failed", team=self) from exc

    @staticmethod
    def _local_context(
        assignment: dict[str, Any],
        upstream: dict[str, Any] | None = None,
        feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "materials": assignment["context"],
            "upstream": {} if upstream is None else dict(upstream),
            "feedback": {} if feedback is None else dict(feedback),
        }

    async def execute(self, task: Any, context: Any) -> Any:
        """Allocate this invocation, then return its collaboration's business result."""
        assignments = await self.allocate(task, context)
        if self._pattern is PatternKind.SEQUENTIAL:
            return await self._run_sequential(assignments)
        if self._pattern is PatternKind.PARALLEL:
            return await self._run_parallel(assignments)
        if self._pattern is PatternKind.ROUTER:
            return await self._run_router(assignments, task, context)
        return await self._run_loop(assignments, context)

    async def _run_sequential(
        self, assignments: dict[str, dict[str, Any]], feedback: dict[str, Any] | None = None
    ) -> Any:
        previous: dict[str, Any] = {}
        result = None
        for name, member in self._members.items():
            assignment = assignments[name]
            result = await member.execute(
                assignment["task"], self._local_context(assignment, previous, feedback)
            )
            previous = {name: result}
        return result

    async def _run_parallel(self, assignments: dict[str, dict[str, Any]]) -> dict[str, Any]:
        async def execute_member(name: str, member: TeamMember) -> Any:
            assignment = assignments[name]
            return await member.execute(assignment["task"], self._local_context(assignment))

        pending = [
            asyncio.create_task(execute_member(name, member))
            for name, member in self._members.items()
        ]
        collected = asyncio.gather(*pending)
        try:
            results = await asyncio.shield(collected)
        except BaseException:
            for child in pending:
                if not child.done():
                    child.cancel()
            await asyncio.gather(collected, *pending, return_exceptions=True)
            raise
        return dict(zip(self._members, results, strict=True))

    async def _run_router(self, assignments: dict[str, dict[str, Any]], task: Any, context: Any) -> Any:
        assert self._selector is not None  # Guaranteed by the fixed construction mode.
        selected = self._selector(task, context)
        if not isinstance(selected, str):
            raise TypeError("selector must return a string member name")
        if selected not in self._members:
            raise LookupError(f"selector returned {selected!r}, available: {list(self._members)!r}")
        assignment = assignments[selected]
        return await self._members[selected].execute(
            assignment["task"], self._local_context(assignment)
        )

    async def _run_loop(self, assignments: dict[str, dict[str, Any]], context: Any) -> Any:
        # Context belongs to the caller. Exhaustion fields conflict across nested
        # and repeated runs; exhaustion is application semantics.
        assert self._until is not None and self._max_iterations is not None
        feedback: dict[str, Any] = {}
        result = None
        for _ in range(self._max_iterations):
            result = await self._run_sequential(assignments, feedback)
            done = self._until(result, context)
            if not isinstance(done, bool):
                raise TypeError("until must return bool")
            if done:
                return result
            feedback = {"result": result}
        return result
