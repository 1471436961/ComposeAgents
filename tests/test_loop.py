"""Bounded rounds, strict predicates, live feedback and application-owned context."""

import asyncio
from types import MappingProxyType

import pytest

from nooa_patterns import Loop, Members, Team, as_member


def test_max_iterations_is_required_and_keyword_only() -> None:
    with pytest.raises(TypeError):
        Loop(lambda task, context: True)
    with pytest.raises(TypeError):
        Loop(lambda task, context: True, 2)


@pytest.mark.parametrize("limit", [True, False, 2.0, "2", None])
def test_non_integer_and_boolean_bounds_are_rejected(limit) -> None:
    with pytest.raises(TypeError, match="max_iterations must be an int"):
        Loop(lambda task, context: True, max_iterations=limit)


@pytest.mark.parametrize("limit", [0, -1, -3])
def test_nonpositive_integer_bounds_are_rejected(limit: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        Loop(lambda task, context: True, max_iterations=limit)


@pytest.mark.parametrize("decision", [1, 0, None, "done", []])
def test_predicate_must_return_bool_without_coercion(decision) -> None:
    calls: list[str] = []

    async def member(task: object, context: object) -> object:
        calls.append("member")
        return task

    def until(result: object, context: object):
        calls.append("until")
        return decision

    with pytest.raises(TypeError, match="until must return bool"):
        asyncio.run(Team([as_member(member)], Loop(until, max_iterations=3)).execute(None, None))
    assert calls == ["member", "until"]


def test_predicate_result_is_not_tested_with_implicit_truthiness() -> None:
    class Truthy:
        def __bool__(self) -> bool:
            raise AssertionError("Must reject the type without coercing it")

    async def member(task, context):
        return task

    loop = Loop(lambda result, context: Truthy(), max_iterations=1)
    with pytest.raises(TypeError, match="until must return bool"):
        asyncio.run(Team([as_member(member)], loop).execute(None, None))


def test_first_round_runs_before_predicate_even_when_it_would_immediately_succeed() -> None:
    entry, final, context = object(), object(), object()
    events: list[str] = []

    async def member(task: object, shared: object) -> object:
        assert task is entry and shared is context
        events.append("member")
        return final

    def until(result: object, shared: object) -> bool:
        assert result is final and shared is context
        assert events == ["member"]
        events.append("until")
        return True

    result = asyncio.run(Team([as_member(member)], Loop(until, max_iterations=3)).execute(entry, context))
    assert result is final and events == ["member", "until"]


def test_mapping_order_complete_rounds_and_last_results_feed_the_next_round() -> None:
    context = object()
    events: list[tuple[str, int]] = []

    async def increment(task: int, shared: object) -> int:
        assert shared is context
        events.append(("increment", task))
        return task + 1

    async def double(task: int, shared: object) -> int:
        assert shared is context
        events.append(("double", task))
        return task * 2

    def until(result: int, shared: object) -> bool:
        assert shared is context
        events.append(("until", result))
        return result >= 10

    team = Team({"increment": as_member(increment), "double": as_member(double)},
                Loop(until, max_iterations=5))
    assert asyncio.run(team.execute(0, context)) == 14
    assert events == [("increment", 0), ("double", 1), ("until", 2),
                      ("increment", 2), ("double", 3), ("until", 6),
                      ("increment", 6), ("double", 7), ("until", 14)]


@pytest.mark.parametrize(("target", "expected_rounds", "exhausted"),
                         [(1, 1, False), (3, 3, False), (4, 3, True)],
                         ids=["early", "last-allowed", "exhausted"])
def test_application_closure_observes_stop_vs_exhaustion_and_original_result(
    target: int, expected_rounds: int, exhausted: bool
) -> None:
    sentinel = object()
    context = MappingProxyType({"loop_exhausted": sentinel})
    entry = {"value": 0}
    inputs, outputs = [], []
    rounds, last_ok = 0, False

    async def step(task: dict[str, int], shared: object) -> dict[str, int]:
        assert shared is context
        inputs.append(task)
        result = {"value": task["value"] + 1}
        outputs.append(result)
        return result

    def until(result: dict[str, int], shared: object) -> bool:
        nonlocal rounds, last_ok
        assert shared is context and result is outputs[-1]
        rounds += 1
        last_ok = result["value"] >= target
        return last_ok

    result = asyncio.run(Team([as_member(step)], Loop(until, max_iterations=3)).execute(entry, context))
    assert rounds == expected_rounds
    assert (rounds == 3 and not last_ok) is exhausted
    assert inputs[0] is entry and result is outputs[-1]
    assert all(inputs[i] is outputs[i - 1] for i in range(1, rounds))
    assert result["value"] == expected_rounds
    assert dict(context) == {"loop_exhausted": sentinel}


def test_none_is_a_normal_round_result_and_next_round_input() -> None:
    entry, context = object(), {}
    received: list[object] = []
    rounds = 0

    async def member(task: object, shared: object) -> None:
        assert shared is context
        received.append(task)
        return None

    def until(result: None, shared: object) -> bool:
        nonlocal rounds
        assert result is None and shared is context
        rounds += 1
        return rounds == 2

    assert asyncio.run(Team([as_member(member)], Loop(until, max_iterations=3)).execute(entry, context)) is None
    assert received[0] is entry and received[1] is None
    assert rounds == 2 and context == {}


def test_member_failure_stops_the_round_and_preserves_effects_without_retry() -> None:
    failure = ValueError("failed in round two")
    sentinel = object()
    context = {"loop_exhausted": sentinel, "events": []}

    async def prepare(task: int, shared: dict) -> int:
        shared["events"].append(("prepare", task))
        return task + 1

    async def fail_second_round(task: int, shared: dict) -> int:
        shared["events"].append(("work", task))
        if task == 2:
            raise failure
        return task

    async def later(task: int, shared: dict) -> int:
        shared["events"].append(("later", task))
        return task

    def until(result: int, shared: dict) -> bool:
        shared["events"].append(("until", result))
        return False

    team = Team([as_member(prepare), as_member(fail_second_round), as_member(later)],
                Loop(until, max_iterations=3))
    with pytest.raises(ValueError) as caught:
        asyncio.run(team.execute(0, context))
    assert caught.value is failure and context["loop_exhausted"] is sentinel
    assert context["events"] == [("prepare", 0), ("work", 1), ("later", 1), ("until", 1),
                                 ("prepare", 1), ("work", 2)]


@pytest.mark.parametrize("failure", [ValueError("until failed"), asyncio.CancelledError()],
                         ids=["exception", "cancellation"])
def test_until_failure_propagates_after_complete_round_without_recording_exhaustion(failure) -> None:
    context = MappingProxyType({"loop_exhausted": object()})
    original = dict(context)
    calls: list[str] = []

    async def step(task, shared):
        assert shared is context
        calls.append("step")
        return task

    def until(result, shared):
        assert shared is context
        calls.append("until")
        raise failure

    team = Team([as_member(step), as_member(step)], Loop(until, max_iterations=3))
    with pytest.raises(type(failure)) as caught:
        asyncio.run(team.execute(None, context))
    assert caught.value is failure
    assert calls == ["step", "step", "until"] and dict(context) == original


def test_outer_cancellation_waits_for_member_cleanup_and_stops_later_work() -> None:
    context = {"events": [], "loop_exhausted": object()}
    sentinel = context["loop_exhausted"]

    async def scenario() -> None:
        started, cancelled, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def wait(task, shared):
            shared["events"].append("started")
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                await release.wait()
                shared["events"].append("cleaned")
                raise

        async def never(task, shared):
            raise AssertionError("Later members must not start")

        def until(result, shared):
            raise AssertionError("Incomplete rounds must not call until")

        team = Team([as_member(wait), as_member(never)], Loop(until, max_iterations=3))
        async with asyncio.timeout(5):
            running = asyncio.create_task(team.execute(None, context))
            await started.wait()
            running.cancel()
            await cancelled.wait()
            assert not running.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await running

    asyncio.run(scenario())
    assert context["events"] == ["started", "cleaned"]
    assert context["loop_exhausted"] is sentinel


def test_nested_loops_share_readonly_context_without_overwriting_each_other() -> None:
    sentinel = object()
    context = MappingProxyType({"loop_exhausted": sentinel, "rounds": sentinel})
    decisions = []

    async def increment(task: int, shared: object) -> int:
        assert shared is context
        return task + 1

    def inner_until(result: int, shared: object) -> bool:
        assert shared is context
        decisions.append(("inner", result))
        return False

    def outer_until(result: int, shared: object) -> bool:
        assert shared is context
        decisions.append(("outer", result))
        return False

    inner = Team([as_member(increment)], Loop(inner_until, max_iterations=2))
    outer = Team([inner, as_member(increment)], Loop(outer_until, max_iterations=2))
    assert asyncio.run(outer.execute(0, context)) == 6
    assert decisions == [("inner", 1), ("inner", 2), ("outer", 3),
                         ("inner", 4), ("inner", 5), ("outer", 6)]
    assert dict(context) == {"loop_exhausted": sentinel, "rounds": sentinel}


def test_shared_loop_keeps_interleaved_and_repeated_runs_independent() -> None:
    async def scenario() -> None:
        started, resume = asyncio.Event(), asyncio.Event()
        context_a = {"target": 3, "calls": []}
        context_b = {"target": 11, "calls": []}

        async def step(task: int, context: dict) -> int:
            context["calls"].append(task)
            if context is context_a and task == 0:
                started.set()
                await resume.wait()
            return task + 1

        loop = Loop(lambda result, context: result >= context["target"], max_iterations=3)
        a, b = Team([as_member(step)], loop), Team([as_member(step)], loop)
        async with asyncio.timeout(5):
            running = asyncio.create_task(a.execute(0, context_a))
            await started.wait()
            assert await b.execute(10, context_b) == 11
            assert not running.done()
            resume.set()
            assert await running == 3
            fresh = {"target": 2, "calls": []}
            assert await a.execute(0, fresh) == 2
        assert context_a["calls"] == [0, 1, 2]
        assert context_b["calls"] == [10] and fresh["calls"] == [0, 1]

    asyncio.run(scenario())


def test_incompatible_feedback_is_not_automatically_converted() -> None:
    received = []

    async def requires_int(task: int, context: object) -> str:
        received.append(task)
        if not isinstance(task, int):
            raise TypeError("Application input must be int")
        return "a report, not the next integer input"

    with pytest.raises(TypeError, match="Application input must be int"):
        asyncio.run(Team([as_member(requires_int)], Loop(lambda r, c: False, max_iterations=2))
                    .execute(1, None))
    assert received == [1, "a report, not the next integer input"]


@pytest.mark.parametrize("members", [[], {}], ids=["sequence", "mapping"])
def test_empty_team_is_rejected_at_construction(members) -> None:
    with pytest.raises(ValueError, match="at least one member"):
        Team(members, Loop(lambda result, context: True, max_iterations=1))


def test_direct_empty_run_is_rejected_before_the_predicate() -> None:
    def until(result, context):
        raise AssertionError("Empty rounds must not call until")

    with pytest.raises(ValueError, match="at least one member"):
        asyncio.run(Loop(until, max_iterations=1).run(Members([]), None, None))
