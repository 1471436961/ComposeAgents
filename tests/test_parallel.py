"""Ordered fan-in, live references and cooperative fail-fast cleanup."""

import asyncio

import pytest

from nooa_patterns import Parallel, Sequential, Team


def test_concurrent_calls_keep_input_references_and_member_result_order() -> None:
    task = {"proposal": "shared input"}
    context: list[str] = []
    results = [{"feasible": True}, None, ["cost"]]
    completed: list[int] = []

    async def scenario() -> None:
        started = [asyncio.Event() for _ in results]
        release = [asyncio.Event() for _ in results]
        finished = [asyncio.Event() for _ in results]

        class Controlled:
            def __init__(self, index: int) -> None:
                self.index = index
                self.calls = 0

            async def execute(self, value: object, shared: list[str]) -> object:
                assert value is task
                assert shared is context
                self.calls += 1
                started[self.index].set()
                await release[self.index].wait()
                shared.append(str(self.index))
                completed.append(self.index)
                finished[self.index].set()
                return results[self.index]

        members = [Controlled(i) for i in range(3)]
        async with asyncio.timeout(5):
            running = asyncio.create_task(Team(members, Parallel()).execute(task, context))
            await asyncio.gather(*(event.wait() for event in started))
            assert not running.done()  # Every member started before any could finish.
            for index in (2, 1, 0):
                release[index].set()
                await finished[index].wait()
            actual = await running

        assert isinstance(actual, list)
        assert actual is not results
        assert len(actual) == 3
        assert all(actual[i] is results[i] for i in range(3))
        assert all(member.calls == 1 for member in members)

    asyncio.run(scenario())
    assert completed == [2, 1, 0]
    assert context == ["2", "1", "0"]
    assert task == {"proposal": "shared input"}


@pytest.mark.parametrize("result", [None, {"report": ["done"]}], ids=["none", "object"])
def test_one_member_returns_one_element_list_with_original_result(result: object) -> None:
    class Only:
        async def execute(self, task: object, context: object) -> object:
            return result

    actual = asyncio.run(Team([Only()], Parallel()).execute(object(), object()))
    assert isinstance(actual, list)
    assert len(actual) == 1
    assert actual[0] is result


def test_empty_team_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError):
        Team([], Parallel())


def test_direct_empty_run_is_rejected() -> None:
    with pytest.raises(ValueError):
        asyncio.run(Parallel().run((), object(), object()))


def test_failure_cancels_siblings_and_waits_for_cleanup_before_original_error() -> None:
    failure = ValueError("planned analysis failure")
    context: list[str] = []

    async def scenario() -> None:
        started = [asyncio.Event(), asyncio.Event()]
        cancelled = [asyncio.Event(), asyncio.Event()]
        release_cleanup = asyncio.Event()
        cleaned: list[int] = []
        children: list[asyncio.Task] = []

        class Waiting:
            def __init__(self, index: int) -> None:
                self.index = index

            async def execute(self, task: object, shared: list[str]) -> object:
                children.append(asyncio.current_task())
                shared.append(f"started {self.index}")
                started[self.index].set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled[self.index].set()
                    raise
                finally:
                    await release_cleanup.wait()
                    cleaned.append(self.index)

        class Failing:
            async def execute(self, task: object, shared: list[str]) -> object:
                children.append(asyncio.current_task())
                await asyncio.gather(*(event.wait() for event in started))
                shared.append("effect before failure")
                raise failure

        async with asyncio.timeout(5):
            running = asyncio.create_task(
                Team([Waiting(0), Failing(), Waiting(1)], Parallel()).execute(object(), context)
            )
            await asyncio.gather(*(event.wait() for event in cancelled))
            assert not running.done()
            assert cleaned == []
            release_cleanup.set()
            with pytest.raises(ValueError) as caught:
                await running
            assert caught.value is failure
            assert sorted(cleaned) == [0, 1]
            assert all(child.done() for child in children)

    asyncio.run(scenario())
    assert context.count("effect before failure") == 1
    assert len(context) == 3


def test_outer_cancellation_reaches_all_members_and_waits_for_async_cleanup() -> None:
    context: list[int] = []

    async def scenario() -> None:
        started = [asyncio.Event() for _ in range(3)]
        cancelled = [asyncio.Event() for _ in range(3)]
        release_cleanup = asyncio.Event()
        cleaned: list[int] = []
        children: list[asyncio.Task] = []

        class Waiting:
            def __init__(self, index: int) -> None:
                self.index = index

            async def execute(self, task: object, shared: list[int]) -> object:
                children.append(asyncio.current_task())
                shared.append(self.index)
                started[self.index].set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled[self.index].set()
                    raise
                finally:
                    await release_cleanup.wait()
                    cleaned.append(self.index)

        async with asyncio.timeout(5):
            running = asyncio.create_task(
                Team([Waiting(i) for i in range(3)], Parallel()).execute(object(), context)
            )
            await asyncio.gather(*(event.wait() for event in started))
            running.cancel()
            await asyncio.gather(*(event.wait() for event in cancelled))
            assert not running.done()
            assert cleaned == []
            release_cleanup.set()
            with pytest.raises(asyncio.CancelledError):
                await running
            assert sorted(cleaned) == [0, 1, 2]
            assert all(child.done() and child.cancelled() for child in children)

    asyncio.run(scenario())
    assert sorted(context) == [0, 1, 2]


def test_member_cancellation_aborts_collection_and_cancels_peer() -> None:
    async def scenario() -> None:
        peer_started = asyncio.Event()
        peer_cancelled = asyncio.Event()

        class Waiting:
            async def execute(self, task: object, context: object) -> object:
                peer_started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    peer_cancelled.set()
                    raise

        class SelfCancelled:
            async def execute(self, task: object, context: object) -> object:
                await peer_started.wait()
                raise asyncio.CancelledError("member cancelled")

        async with asyncio.timeout(5):
            with pytest.raises(asyncio.CancelledError):
                await Team([Waiting(), SelfCancelled()], Parallel()).execute(object(), object())
        assert peer_cancelled.is_set()

    asyncio.run(scenario())


def test_outer_cancellation_is_not_replaced_by_a_members_cleanup_exception() -> None:
    async def scenario() -> None:
        started = [asyncio.Event(), asyncio.Event()]
        cancelled = [asyncio.Event(), asyncio.Event()]
        cleanup_failed = asyncio.Event()
        release_cleanup = asyncio.Event()
        cleaned = asyncio.Event()
        children: list[asyncio.Task] = []

        class Waiting:
            def __init__(self, index: int) -> None:
                self.index = index

            async def execute(self, task: object, context: object) -> object:
                children.append(asyncio.current_task())
                started[self.index].set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled[self.index].set()
                    raise
                finally:
                    if self.index == 0:
                        cleanup_failed.set()
                        raise RuntimeError("error while cleaning up cancellation")
                    await release_cleanup.wait()
                    cleaned.set()

        async with asyncio.timeout(5):
            running = asyncio.create_task(
                Team([Waiting(0), Waiting(1)], Parallel()).execute(object(), object())
            )
            await asyncio.gather(*(event.wait() for event in started))
            running.cancel()
            await cleanup_failed.wait()
            assert not running.done()
            release_cleanup.set()
            with pytest.raises(asyncio.CancelledError):
                await running
        assert all(event.is_set() for event in cancelled)
        assert cleaned.is_set()
        assert all(child.done() for child in children)

    asyncio.run(scenario())


def test_outer_cancellation_during_failure_cleanup_takes_precedence() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        cleanup_started = asyncio.Event()
        cleaned = asyncio.Event()

        class Waiting:
            async def execute(self, task: object, context: object) -> object:
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleanup_started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        cleaned.set()

        class Failing:
            async def execute(self, task: object, context: object) -> object:
                await started.wait()
                raise ValueError("business failure before outer cancellation")

        async with asyncio.timeout(5):
            running = asyncio.create_task(
                Team([Waiting(), Failing()], Parallel()).execute(object(), object())
            )
            await cleanup_started.wait()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
        assert cleaned.is_set()

    asyncio.run(scenario())


def test_cleanup_exception_does_not_replace_triggering_business_error() -> None:
    failure = ValueError("business failure")
    cleanup_failure = RuntimeError("cleanup failure")

    async def scenario() -> None:
        started = asyncio.Event()
        cleaned = asyncio.Event()
        children: list[asyncio.Task] = []

        class Waiting:
            async def execute(self, task: object, context: object) -> object:
                children.append(asyncio.current_task())
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned.set()
                    raise cleanup_failure

        class Failing:
            async def execute(self, task: object, context: object) -> object:
                await started.wait()
                raise failure

        async with asyncio.timeout(5):
            with pytest.raises(ValueError) as caught:
                await Parallel().run((Waiting(), Failing()), object(), object())
        assert caught.value is failure
        assert cleaned.is_set()
        assert children[0].done()

    asyncio.run(scenario())


def test_simultaneous_failures_propagate_one_original_without_grouping() -> None:
    failures = [ValueError("one"), ValueError("two")]

    async def scenario() -> None:
        ready = [asyncio.Event(), asyncio.Event()]
        release = asyncio.Event()
        children: list[asyncio.Task] = []

        class Failing:
            def __init__(self, index: int) -> None:
                self.index = index

            async def execute(self, task: object, context: object) -> object:
                children.append(asyncio.current_task())
                ready[self.index].set()
                await release.wait()
                raise failures[self.index]

        async with asyncio.timeout(5):
            running = asyncio.create_task(
                Parallel().run((Failing(0), Failing(1)), object(), object())
            )
            await asyncio.gather(*(event.wait() for event in ready))
            release.set()
            with pytest.raises(ValueError) as caught:
                await running
        assert any(caught.value is failure for failure in failures)
        assert all(child.done() for child in children)

    asyncio.run(scenario())


def test_nested_failure_cancels_both_inner_and_outer_siblings() -> None:
    failure = ValueError("nested failure")

    async def scenario() -> None:
        started = [asyncio.Event(), asyncio.Event()]
        cancelled = [asyncio.Event(), asyncio.Event()]

        class Waiting:
            def __init__(self, index: int) -> None:
                self.index = index

            async def execute(self, task: object, context: object) -> object:
                started[self.index].set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled[self.index].set()
                    raise

        class Failing:
            async def execute(self, task: object, context: object) -> object:
                await asyncio.gather(*(event.wait() for event in started))
                raise failure

        child = Team([Failing(), Waiting(0)], Parallel())
        outer = Team([child, Waiting(1)], Parallel())
        async with asyncio.timeout(5):
            with pytest.raises(ValueError) as caught:
                await outer.execute(object(), object())
        assert caught.value is failure
        assert all(event.is_set() for event in cancelled)

    asyncio.run(scenario())


def test_shared_pattern_failure_does_not_cancel_another_teams_run() -> None:
    pattern = Parallel()
    task_a, result_a = object(), object()
    context_a: list[str] = []
    context_b: list[str] = []
    failure = ValueError("B failed")

    async def scenario() -> None:
        a_started = asyncio.Event()
        release_a = asyncio.Event()
        b_started = asyncio.Event()

        class WaitingA:
            async def execute(self, task: object, context: list[str]) -> object:
                assert task is task_a
                assert context is context_a
                context.append("started")
                a_started.set()
                await release_a.wait()
                context.append("done")
                return result_a

        class WaitingB:
            async def execute(self, task: object, context: list[str]) -> object:
                assert context is context_b
                b_started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    context.append("cancelled")

        class FailingB:
            async def execute(self, task: object, context: list[str]) -> object:
                await b_started.wait()
                raise failure

        first = Team([WaitingA()], pattern)
        second = Team([WaitingB(), FailingB()], pattern)
        assert first.pattern is second.pattern is pattern
        async with asyncio.timeout(5):
            running_a = asyncio.create_task(first.execute(task_a, context_a))
            await a_started.wait()
            with pytest.raises(ValueError) as caught:
                await second.execute(object(), context_b)
            assert caught.value is failure
            assert not running_a.done()
            assert context_a == ["started"]
            release_a.set()
            result = await running_a
            assert len(result) == 1 and result[0] is result_a

    asyncio.run(scenario())
    assert context_a == ["started", "done"]
    assert context_b == ["cancelled"]


def test_outer_cancellation_reaches_nested_children_without_undoing_completed_work() -> None:
    context: list[str] = []

    async def scenario() -> None:
        started = [asyncio.Event() for _ in range(3)]
        cancelled = [asyncio.Event() for _ in range(3)]
        release_cleanup = asyncio.Event()
        cleaned: list[int] = []
        completed_jobs: list[asyncio.Task] = []

        class Waiting:
            def __init__(self, index: int) -> None:
                self.index = index

            async def execute(self, task: object, shared: list[str]) -> object:
                started[self.index].set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled[self.index].set()
                    raise
                finally:
                    await release_cleanup.wait()
                    cleaned.append(self.index)

        class Completed:
            async def execute(self, task: object, shared: list[str]) -> object:
                completed_jobs.append(asyncio.current_task())
                shared.append("completed effect")
                return task

        child = Team([Waiting(0), Waiting(1)], Parallel())
        outer = Team([child, Completed(), Waiting(2)], Parallel())
        async with asyncio.timeout(5):
            running = asyncio.create_task(outer.execute(object(), context))
            await asyncio.gather(*(event.wait() for event in started))
            assert len(completed_jobs) == 1 and completed_jobs[0].done()
            running.cancel()
            await asyncio.gather(*(event.wait() for event in cancelled))
            assert not running.done()
            release_cleanup.set()
            with pytest.raises(asyncio.CancelledError):
                await running
        assert sorted(cleaned) == [0, 1, 2]
        assert not completed_jobs[0].cancelled()

    asyncio.run(scenario())
    assert context == ["completed effect"]


def test_a_member_suppressing_cancellation_does_not_turn_the_run_into_success() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        returned: list[object] = []
        result = object()

        class SuppressesCancellation:
            async def execute(self, task: object, context: object) -> object:
                started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    returned.append(result)
                    return result

        async with asyncio.timeout(5):
            running = asyncio.create_task(
                Team([SuppressesCancellation()], Parallel()).execute(object(), object())
            )
            await started.wait()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
        assert len(returned) == 1 and returned[0] is result

    asyncio.run(scenario())


def test_compatible_members_can_change_pattern_with_explicit_output_shape() -> None:
    task = object()
    calls: list[tuple[object, object]] = []

    class Echo:
        async def execute(self, value: object, context: object) -> object:
            calls.append((value, context))
            return value

    members = [Echo(), Echo(), Echo()]
    sequential = Team(members, Sequential())
    parallel = Team(members, Parallel())
    context_a, context_b = object(), object()

    async def scenario() -> None:
        assert await sequential.execute(task, context_a) is task
        result = await parallel.execute(task, context_b)
        assert isinstance(result, list)
        assert len(result) == 3 and all(value is task for value in result)

    asyncio.run(scenario())
    assert all(sequential.members[i] is parallel.members[i] is members[i] for i in range(3))
    assert len(calls) == 6
    assert all(value is task for value, _ in calls)
    assert all(shared is context_a for _, shared in calls[:3])
    assert all(shared is context_b for _, shared in calls[3:])
