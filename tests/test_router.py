"""Named routing preserves one-call, reference, failure and nesting contracts."""

import asyncio

import pytest

from nooa_patterns import Members, Parallel, Router, Sequential, Team, as_member


class _Result:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[object, object]] = []

    async def execute(self, task: object, context: object) -> object:
        self.calls.append((task, context))
        return self.result


def test_router_rejects_sequence_at_team_construction_without_running_selector() -> None:
    decisions: list[object] = []

    def selector(task: object, context: object) -> str:
        decisions.append(task)
        return "security"

    member = _Result(object())
    with pytest.raises(ValueError, match="^Router requires named members$"):
        Team([member], Router(selector))
    assert decisions == [] and member.calls == []


def test_router_rejects_empty_mapping_at_team_construction() -> None:
    with pytest.raises(ValueError, match="at least one member"):
        Team({}, Router(lambda task, context: "security"))


def test_unknown_name_lists_available_names_from_the_snapshot() -> None:
    members = {name: _Result(object()) for name in ("security", "architecture", "quick")}
    originals = list(members.values())
    task, context = object(), object()
    decisions: list[tuple[object, object]] = []

    def selector(value: object, shared: object) -> str:
        decisions.append((value, shared))
        return "unknown"

    team = Team(members, Router(selector))
    members.clear()
    members["replacement"] = _Result(object())
    with pytest.raises(LookupError) as caught:
        asyncio.run(team.execute(task, context))
    assert str(caught.value) == (
        "selector returned 'unknown', available: ['security', 'architecture', 'quick']"
    )
    assert len(decisions) == 1 and decisions[0][0] is task and decisions[0][1] is context
    assert all(member.calls == [] for member in originals)


@pytest.mark.parametrize("result", [None, {"review": "accepted"}], ids=["none", "object"])
def test_one_decision_one_member_and_original_arguments_and_result(result: object) -> None:
    task, context = object(), {"events": []}
    chosen, other = _Result(result), _Result(object())
    decisions: list[tuple[object, object]] = []

    def selector(value: object, shared: object) -> str:
        decisions.append((value, shared))
        return "architecture"

    team = Team({"security": other, "architecture": chosen}, Router(selector))
    assert asyncio.run(team.execute(task, context)) is result
    assert len(decisions) == len(chosen.calls) == 1
    assert decisions[0][0] is chosen.calls[0][0] is task
    assert decisions[0][1] is chosen.calls[0][1] is context
    assert context == {"events": []} and other.calls == []


@pytest.mark.parametrize("failure", [ValueError("decision failed"), asyncio.CancelledError()])
def test_selector_failure_or_cancellation_is_propagated_without_calling_members(failure) -> None:
    member = _Result(object())
    decisions: list[object] = []

    def selector(task: object, context: object) -> str:
        decisions.append(task)
        raise failure

    with pytest.raises(type(failure)) as caught:
        asyncio.run(Team({"only": member}, Router(selector)).execute(object(), object()))
    assert caught.value is failure
    assert len(decisions) == 1 and member.calls == []


@pytest.mark.parametrize("selected", [0, None, []], ids=["index", "none", "list"])
def test_non_string_selection_is_rejected_instead_of_using_an_index(selected) -> None:
    member = _Result(object())
    with pytest.raises(TypeError, match="member name as str"):
        asyncio.run(Team({"0": member}, Router(lambda task, context: selected)).execute(None, None))
    assert member.calls == []


def test_selected_member_failure_keeps_effects_and_does_not_fall_back_or_retry() -> None:
    failure = ValueError("review failed")
    context: list[str] = []
    other = _Result(object())

    async def fail(task: object, shared: list[str]) -> object:
        shared.append("selected")
        raise failure

    with pytest.raises(ValueError) as caught:
        asyncio.run(Team({"fail": as_member(fail), "other": other}, Router(lambda t, c: "fail"))
                    .execute(object(), context))
    assert caught.value is failure
    assert context == ["selected"] and other.calls == []


def test_outer_cancellation_reaches_only_selected_member_and_waits_for_its_cleanup() -> None:
    context: list[str] = []
    other = _Result(object())

    async def scenario() -> None:
        started, cancelled, finish_cleanup = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def wait(task: object, shared: list[str]) -> object:
            shared.append("started")
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                await finish_cleanup.wait()
                shared.append("cleaned")
                raise

        team = Team({"wait": as_member(wait), "other": other}, Router(lambda t, c: "wait"))
        async with asyncio.timeout(5):
            running = asyncio.create_task(team.execute(object(), context))
            await started.wait()
            running.cancel()
            await cancelled.wait()
            assert not running.done() and other.calls == []
            finish_cleanup.set()
            with pytest.raises(asyncio.CancelledError):
                await running

    asyncio.run(scenario())
    assert context == ["started", "cleaned"] and other.calls == []


def test_selected_child_team_keeps_its_parallel_pattern_and_business_result() -> None:
    first, second = _Result(object()), _Result(object())
    other = _Result(object())
    task, context = object(), object()
    pattern = Parallel()
    child = Team([first, second], pattern)
    parent = Team({"department": child, "other": other}, Router(lambda t, c: "department"))

    result = asyncio.run(parent.execute(task, context))
    assert parent.members["department"] is child and child.pattern is pattern
    assert isinstance(result, list) and len(result) == 2
    assert result[0] is first.result and result[1] is second.result
    assert first.calls[0][0] is second.calls[0][0] is task
    assert first.calls[0][1] is second.calls[0][1] is context
    assert other.calls == []


def test_changing_selector_reuses_the_same_business_members() -> None:
    security, quick = _Result(object()), _Result(object())
    members = {"security": security, "quick": quick}
    conservative = Team(members, Router(lambda t, c: "security"))
    fast = Team(members, Router(lambda t, c: "quick"))
    task, context = object(), object()

    assert asyncio.run(conservative.execute(task, context)) is security.result
    assert asyncio.run(fast.execute(task, context)) is quick.result
    assert all(conservative.members[name] is fast.members[name] is members[name] for name in members)
    assert len(security.calls) == len(quick.calls) == 1


def test_shared_router_does_not_mix_choices_between_interleaved_teams() -> None:
    async def scenario() -> None:
        started, resume = asyncio.Event(), asyncio.Event()
        a_result, b_result = object(), object()
        a_context, b_context = [], []

        async def pause(task: dict[str, str], context: list[str]) -> object:
            assert task["route"] == "pause" and context is a_context
            started.set()
            await resume.wait()
            context.append("A")
            return a_result

        async def finish(task: dict[str, str], context: list[str]) -> object:
            assert task["route"] == "finish" and context is b_context
            context.append("B")
            return b_result

        router = Router(lambda task, context: task["route"])
        a = Team({"pause": as_member(pause)}, router)
        b = Team({"finish": as_member(finish)}, router)
        async with asyncio.timeout(5):
            running = asyncio.create_task(a.execute({"route": "pause"}, a_context))
            await started.wait()
            assert await b.execute({"route": "finish"}, b_context) is b_result
            assert not running.done()
            resume.set()
            assert await running is a_result
        assert a_context == ["A"] and b_context == ["B"]

    asyncio.run(scenario())


def test_named_requirement_is_a_declaration_not_a_router_class_name_guess() -> None:
    class PickLast:
        requires_named_members = True

        async def run(self, members: Members, task: object, context: object) -> object:
            return await members[members.names[-1]].execute(task, context)

    member = _Result(object())
    with pytest.raises(ValueError, match="PickLast requires named members"):
        Team([member], PickLast())
    assert asyncio.run(Team({"last": member}, PickLast()).execute(None, None)) is member.result


@pytest.mark.parametrize("pattern", [Sequential(), Parallel()], ids=["sequential", "parallel"])
def test_existing_patterns_iterate_mapping_values_in_their_original_contract(pattern) -> None:
    first, second = _Result(object()), _Result(object())
    task, context = object(), object()
    team = Team({"first": first, "second": second}, pattern)
    result = asyncio.run(team.execute(task, context))
    assert first.calls[0][0] is task
    assert first.calls[0][1] is second.calls[0][1] is context
    if isinstance(pattern, Sequential):
        assert second.calls[0][0] is first.result and result is second.result
    else:
        assert second.calls[0][0] is task
        assert result[0] is first.result and result[1] is second.result


@pytest.mark.parametrize("source", [[], {}, [_Result(object())]], ids=["empty-list", "empty-map", "unnamed"])
def test_direct_router_run_requires_nonempty_named_members(source) -> None:
    decisions: list[object] = []

    def selector(task: object, context: object) -> str:
        decisions.append(task)
        return "only"

    with pytest.raises(ValueError, match="Router requires named members"):
        asyncio.run(Router(selector).run(Members(source), None, None))
    assert decisions == []
