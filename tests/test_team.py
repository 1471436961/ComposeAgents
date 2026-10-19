"""Recursive Team contracts using ordinary fake members and Patterns."""

import asyncio
from collections.abc import Sequence

import pytest

from nooa_patterns import Sequential, Team, TeamMember


class _ResultMember:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[object, object]] = []

    async def execute(self, task: object, context: object) -> object:
        self.calls.append((task, context))
        return self.result


class _FirstOnly:
    """A stateless test-only Pattern with different behavior from Sequential."""

    async def run(
        self, members: Sequence[TeamMember], task: object, context: object
    ) -> object:
        return await members[0].execute(task, context)


def test_empty_members_are_rejected_at_construction() -> None:
    with pytest.raises(ValueError):
        Team(members=[], pattern=Sequential())


def test_member_sequence_is_a_tuple_snapshot_with_original_instances() -> None:
    first = _ResultMember(object())
    second = _ResultMember(object())
    replacement = _ResultMember(object())
    source = [first, second]
    pattern = Sequential()
    team = Team(members=source, pattern=pattern)

    source[:] = [replacement]

    assert isinstance(team.members, tuple)
    assert len(team.members) == 2
    assert team.members[0] is first
    assert team.members[1] is second
    assert team.pattern is pattern

    task = object()
    context = object()
    result = asyncio.run(team.execute(task, context))

    assert result is second.result
    assert len(first.calls) == len(second.calls) == 1
    assert first.calls[0][0] is task
    assert second.calls[0][0] is first.result
    assert first.calls[0][1] is second.calls[0][1] is context
    assert replacement.calls == []


@pytest.mark.parametrize("business_result", [None, {"report": ["done"]}], ids=["none", "object"])
def test_single_member_result_is_not_wrapped_or_copied(business_result: object) -> None:
    task = object()
    context = {"source": task}
    member = _ResultMember(business_result)
    team = Team(members=[member], pattern=Sequential())

    result = asyncio.run(team.execute(task, context))

    assert result is business_result
    assert len(member.calls) == 1
    assert member.calls[0][0] is task
    assert member.calls[0][1] is context
    assert context == {"source": task}


def test_member_state_is_shared_between_teams_without_reset() -> None:
    member = _ResultMember(object())
    first = Team(members=[member], pattern=Sequential())
    second = Team(members=[member], pattern=Sequential())
    task_a, task_b = object(), object()
    context_a, context_b = object(), object()

    async def scenario() -> None:
        assert await first.execute(task_a, context_a) is member.result
        assert await second.execute(task_b, context_b) is member.result

    asyncio.run(scenario())

    assert first.members[0] is second.members[0] is member
    assert len(member.calls) == 2
    assert member.calls[0][0] is task_a
    assert member.calls[0][1] is context_a
    assert member.calls[1][0] is task_b
    assert member.calls[1][1] is context_b


def test_team_delegates_to_a_custom_pattern() -> None:
    first = _ResultMember(object())
    second = _ResultMember(object())
    task, context = object(), object()
    pattern = _FirstOnly()
    team = Team(members=[first, second], pattern=pattern)

    result = asyncio.run(team.execute(task, context))

    assert team.pattern is pattern
    assert result is first.result
    assert len(first.calls) == 1
    assert first.calls[0][0] is task
    assert first.calls[0][1] is context
    assert second.calls == []


def test_nested_team_keeps_its_own_pattern_and_business_result() -> None:
    selected = _ResultMember(object())
    unselected = _ResultMember(object())
    following = _ResultMember(object())
    child = Team(members=[selected, unselected], pattern=_FirstOnly())
    outer = Team(members=[child, following], pattern=Sequential())
    task, context = object(), object()

    result = asyncio.run(outer.execute(task, context))

    assert outer.members[0] is child
    assert result is following.result
    assert len(selected.calls) == len(following.calls) == 1
    assert selected.calls[0][0] is task
    assert following.calls[0][0] is selected.result
    assert selected.calls[0][1] is following.calls[0][1] is context
    assert unselected.calls == []


def test_two_teams_share_one_sequential_without_interleaved_state() -> None:
    pattern = Sequential()
    task_a, task_b = object(), object()
    middle_a, middle_b = object(), object()
    final_a, final_b = object(), object()
    context_a: list[str] = []
    context_b: list[str] = []
    tail_a = _ResultMember(final_a)
    first_b = _ResultMember(middle_b)
    tail_b = _ResultMember(final_b)

    async def scenario() -> None:
        a_started = asyncio.Event()
        release_a = asyncio.Event()

        class PauseA:
            async def execute(self, task: object, context: list[str]) -> object:
                assert task is task_a
                assert context is context_a
                context.append("paused")
                a_started.set()
                await release_a.wait()
                context.append("resumed")
                return middle_a

        team_a = Team(members=[PauseA(), tail_a], pattern=pattern)
        team_b = Team(members=[first_b, tail_b], pattern=pattern)
        assert team_a.pattern is team_b.pattern is pattern

        async with asyncio.timeout(5):
            running_a = asyncio.create_task(team_a.execute(task_a, context_a))
            await a_started.wait()
            assert not running_a.done()
            assert await team_b.execute(task_b, context_b) is final_b
            assert not running_a.done()
            release_a.set()
            assert await running_a is final_a

    asyncio.run(scenario())

    assert context_a == ["paused", "resumed"]
    assert context_b == []
    assert len(tail_a.calls) == len(first_b.calls) == len(tail_b.calls) == 1
    assert tail_a.calls[0][0] is middle_a
    assert tail_a.calls[0][1] is context_a
    assert first_b.calls[0][0] is task_b
    assert first_b.calls[0][1] is context_b
    assert tail_b.calls[0][0] is middle_b
    assert tail_b.calls[0][1] is context_b


def test_heterogeneous_child_output_is_the_outer_members_business_input() -> None:
    context: list[str] = []
    child_output = "3 + 4"
    business_result = {"formula": child_output}
    received: list[str] = []

    class Expand:
        async def execute(self, task: int, context: list[str]) -> tuple[int, int]:
            assert task == 3
            context.append("expand")
            return task, task + 1

    class Format:
        async def execute(self, task: tuple[int, int], context: list[str]) -> str:
            assert task == (3, 4)
            context.append("format")
            return child_output

    class ConsumeText:
        async def execute(self, task: str, context: list[str]) -> dict[str, str]:
            assert isinstance(task, str)
            assert task is child_output
            context.append("consume")
            received.append(task)
            return business_result

    child = Team(members=[Expand(), Format()], pattern=Sequential())
    outer = Team(members=[child, ConsumeText()], pattern=Sequential())

    result = asyncio.run(outer.execute(3, context))

    assert result is business_result
    assert len(received) == 1
    assert received[0] is child_output
    assert context == ["expand", "format", "consume"]


def test_team_propagates_original_exception_and_keeps_effects() -> None:
    failure = ValueError("planned failure")
    context: list[str] = []

    class Failing:
        async def execute(self, task: object, context: list[str]) -> object:
            context.append("effect before failure")
            raise failure

    team = Team(members=[Failing()], pattern=Sequential())

    with pytest.raises(ValueError) as caught:
        asyncio.run(team.execute(object(), context))

    assert caught.value is failure
    assert context == ["effect before failure"]


def test_team_propagates_cancellation_and_stops_later_members() -> None:
    context: list[str] = []
    following = _ResultMember(object())

    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        class Blocking:
            async def execute(self, task: object, context: list[str]) -> object:
                context.append("started")
                started.set()
                await release.wait()
                context.append("completed")
                return task

        team = Team(members=[Blocking(), following], pattern=Sequential())

        async with asyncio.timeout(5):
            running = asyncio.create_task(team.execute(object(), context))
            await started.wait()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running

    asyncio.run(scenario())

    assert context == ["started"]
    assert following.calls == []
