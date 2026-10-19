"""Result, reference and failure contracts using ordinary fake members."""

import asyncio

import pytest

from nooa_patterns.patterns import Sequential


def test_single_member_returns_its_business_result_by_reference() -> None:
    entry_task = object()
    shared_context: list[str] = []
    business_result = {"report": ["completed"]}

    class OnlyMember:
        async def execute(self, task: object, context: list[str]) -> dict[str, list[str]]:
            assert task is entry_task
            assert context is shared_context
            context.append("called")
            return business_result

    result = asyncio.run(Sequential().run((OnlyMember(),), entry_task, shared_context))

    assert result is business_result
    assert shared_context == ["called"]


def test_awaits_each_member_and_hands_off_live_references() -> None:
    entry_task = ["source"]
    intermediate = {"finding": "scripted analysis"}
    final_result = ["report"]
    shared_context: dict[str, list[str]] = {"events": []}

    async def scenario() -> None:
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        second_started = asyncio.Event()

        class First:
            async def execute(
                self, task: list[str], context: dict[str, list[str]]
            ) -> dict[str, str]:
                assert task is entry_task
                assert context is shared_context
                context["events"].append("first started")
                first_started.set()
                await release_first.wait()
                context["events"].append("first completed")
                return intermediate

        class Second:
            async def execute(
                self, task: dict[str, str], context: dict[str, list[str]]
            ) -> list[str]:
                second_started.set()
                assert task is intermediate
                assert context is shared_context
                assert context["events"] == ["first started", "first completed"]
                context["events"].append("second")
                return final_result

        async with asyncio.timeout(5):
            running = asyncio.create_task(
                Sequential().run((First(), Second()), entry_task, shared_context)
            )
            await first_started.wait()
            assert not second_started.is_set()
            assert shared_context == {"events": ["first started"]}
            release_first.set()
            assert await running is final_result

    asyncio.run(scenario())

    assert shared_context == {"events": ["first started", "first completed", "second"]}
    assert entry_task == ["source"]


@pytest.mark.parametrize(
    ("middle_result", "final_result"),
    [(None, object()), (object(), None), (None, None)],
    ids=["intermediate-none", "final-none", "both-none"],
)
def test_none_is_an_ordinary_intermediate_or_final_result(
    middle_result: object, final_result: object
) -> None:
    entry_task = object()
    shared_context = object()
    received: list[object] = []

    class First:
        async def execute(self, task: object, context: object) -> object:
            assert task is entry_task
            assert context is shared_context
            return middle_result

    class Second:
        async def execute(self, task: object, context: object) -> object:
            assert context is shared_context
            received.append(task)
            return final_result

    result = asyncio.run(Sequential().run((First(), Second()), entry_task, shared_context))

    assert len(received) == 1
    assert received[0] is middle_result
    assert result is final_result


def test_exception_stops_later_members_without_retry_or_rollback() -> None:
    entry_task: dict[str, list[str]] = {"changes": []}
    shared_context: dict[str, list[str]] = {"events": []}
    failure = ValueError("planned member failure")

    class Prepare:
        async def execute(
            self, task: dict[str, list[str]], context: dict[str, list[str]]
        ) -> dict[str, list[str]]:
            task["changes"].append("prepared")
            context["events"].append("prepare")
            return task

    class Failing:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(
            self, task: dict[str, list[str]], context: dict[str, list[str]]
        ) -> dict[str, list[str]]:
            self.calls += 1
            assert task is entry_task
            assert context is shared_context
            task["changes"].append("changed before failure")
            context["events"].append("fail")
            raise failure

    class Later:
        async def execute(
            self, task: dict[str, list[str]], context: dict[str, list[str]]
        ) -> dict[str, list[str]]:
            context["events"].append("later")
            return task

    failing = Failing()
    with pytest.raises(ValueError) as caught:
        asyncio.run(
            Sequential().run((Prepare(), failing, Later()), entry_task, shared_context)
        )

    assert caught.value is failure
    assert failing.calls == 1
    assert entry_task == {"changes": ["prepared", "changed before failure"]}
    assert shared_context == {"events": ["prepare", "fail"]}


def test_cancellation_stops_later_members_and_preserves_effects() -> None:
    entry_task = object()
    shared_context: list[str] = []

    async def scenario() -> None:
        blocking_started = asyncio.Event()
        release = asyncio.Event()

        class Prepare:
            async def execute(self, task: object, context: list[str]) -> object:
                context.append("prepare")
                return task

        class Blocking:
            async def execute(self, task: object, context: list[str]) -> object:
                assert task is entry_task
                assert context is shared_context
                context.append("blocking")
                blocking_started.set()
                await release.wait()
                context.append("completed")
                return task

        class Later:
            async def execute(self, task: object, context: list[str]) -> object:
                context.append("later")
                return task

        async with asyncio.timeout(5):
            running = asyncio.create_task(
                Sequential().run((Prepare(), Blocking(), Later()), entry_task, shared_context)
            )
            await blocking_started.wait()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running

    asyncio.run(scenario())

    assert shared_context == ["prepare", "blocking"]


def test_reused_pattern_keeps_interleaved_runs_independent() -> None:
    pattern = Sequential()
    task_a = object()
    task_b = object()
    result_a = object()
    context_a: list[object] = []
    context_b: list[object] = []

    async def scenario() -> None:
        a_started = asyncio.Event()
        release_a = asyncio.Event()

        class PauseA:
            async def execute(self, task: object, context: list[object]) -> object:
                assert task is task_a
                assert context is context_a
                context.append(task)
                a_started.set()
                await release_a.wait()
                return result_a

        class Echo:
            async def execute(self, task: object, context: list[object]) -> object:
                context.append(task)
                return task

        async with asyncio.timeout(5):
            running_a = asyncio.create_task(pattern.run((PauseA(), Echo()), task_a, context_a))
            await a_started.wait()
            assert await pattern.run((Echo(),), task_b, context_b) is task_b
            release_a.set()
            assert await running_a is result_a

    asyncio.run(scenario())

    assert len(context_a) == 2
    assert context_a[0] is task_a
    assert context_a[1] is result_a
    assert len(context_b) == 1
    assert context_b[0] is task_b
