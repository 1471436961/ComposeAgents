"""Configuration, data flow, recursion and feedback through the public Team API."""

import asyncio
from types import MappingProxyType

import pytest

from nooa_patterns import AllocationError, PatternKind as K, Team, as_member
from conftest import ScriptedTeam


async def echo(task, context):
    return task


def config(kind):
    if kind is K.ROUTER:
        return {"selector": lambda task, context: "only"}
    if kind is K.LOOP:
        return {"until": lambda result, context: True, "max_iterations": 1}
    return {}


@pytest.mark.parametrize("kind", list(K))
@pytest.mark.parametrize("result", [None, {"business": []}])
def test_single_member_is_valid_and_keeps_business_identity(kind, result):
    team = ScriptedTeam({"only": as_member(echo)}, kind, **config(kind))
    actual = asyncio.run(team.execute(result, object()))
    if kind is K.PARALLEL:
        assert list(actual) == ["only"] and actual["only"] is result
    else:
        assert actual is result
    assert len(team.allocations) == 1


@pytest.mark.parametrize("members,exc", [({}, ValueError), ([], TypeError), ({1: object()}, TypeError)])
def test_member_configuration_rejected_early(members, exc):
    with pytest.raises(exc):
        Team(members, K.SEQUENTIAL, llm=None)


@pytest.mark.parametrize("pattern", ["sequential", None, object()])
def test_closed_enum_is_required(pattern):
    with pytest.raises(TypeError):
        Team({"a": as_member(echo)}, pattern, llm=None)


@pytest.mark.parametrize("kwargs,exc", [
    ({"selector": lambda t, c: "a"}, ValueError),
    ({"until": lambda t, c: True}, ValueError),
    ({"max_iterations": 2}, ValueError),
])
def test_mode_parameters_must_match(kwargs, exc):
    with pytest.raises(exc):
        Team({"a": as_member(echo)}, K.SEQUENTIAL, llm=None, **kwargs)


@pytest.mark.parametrize("limit,exc", [(None, TypeError), (True, TypeError), (False, TypeError),
    (2.0, TypeError), ("2", TypeError), (0, ValueError), (-1, ValueError)])
def test_loop_requires_positive_explicit_integer(limit, exc):
    kwargs = {} if limit is None else {"max_iterations": limit}
    with pytest.raises(exc):
        Team({"a": as_member(echo)}, K.LOOP, llm=None, until=lambda r, c: False, **kwargs)


@pytest.mark.parametrize("kind,param", [(K.ROUTER, "selector"), (K.LOOP, "until")])
def test_missing_or_async_decisions_rejected_at_construction(kind, param):
    async def decision(*args):
        return True
    class AsyncDecision:
        async def __call__(self, *args):
            return True
    for fn in (None, 42, decision, AsyncDecision()):
        kwargs = {param: fn}
        if kind is K.LOOP:
            kwargs["max_iterations"] = 1
        with pytest.raises(TypeError):
            Team({"a": as_member(echo)}, kind, llm=None, **kwargs)


def test_member_snapshot_and_pattern_are_read_only_but_members_are_live():
    member = as_member(echo)
    source = {"a": member}
    team = ScriptedTeam(source, K.SEQUENTIAL)
    source.clear()
    assert list(team.members) == ["a"] and team.members["a"] is member
    with pytest.raises(TypeError):
        team.members["b"] = member
    with pytest.raises(AttributeError):
        team.members = {}
    with pytest.raises(AttributeError):
        team.pattern = K.PARALLEL


def test_sequential_preserves_assigned_tasks_and_direct_predecessor_only():
    tasks, materials, results = [object() for _ in range(3)], [object() for _ in range(3)], [None, {"artifact": []}, object()]
    contexts, calls = [], []
    def step(index):
        async def execute(task, context):
            assert task is tasks[index]
            assert context["materials"] is materials[index]
            assert context["feedback"] == {}
            assert set(context["upstream"]) == (set() if index == 0 else {str(index - 1)})
            if index:
                assert context["upstream"][str(index - 1)] is results[index - 1]
            contexts.append(context)
            calls.append(index)
            return results[index]
        return as_member(execute)
    team = ScriptedTeam({str(i): step(i) for i in range(3)}, K.SEQUENTIAL,
        assignments={str(i): {"task": tasks[i], "context": materials[i]} for i in range(3)})
    root = MappingProxyType({"loop_exhausted": "sentinel"})
    assert asyncio.run(team.execute(object(), root)) is results[-1]
    assert calls == [0, 1, 2] and len(team.allocations) == 1
    assert len({id(c) for c in contexts}) == 3
    assert len({id(c["upstream"]) for c in contexts}) == 3
    assert dict(root) == {"loop_exhausted": "sentinel"}


@pytest.mark.parametrize("kind", [K.SEQUENTIAL, K.LOOP, K.ROUTER])
def test_business_errors_keep_identity_and_effects(kind):
    error = ValueError("business failure")
    effects = []
    async def fail(task, context):
        context["materials"].append("effect")
        raise error
    async def forbidden(task, context):
        pytest.fail("later/unselected member ran")
    kwargs = {"selector": lambda t, c: "first"} if kind is K.ROUTER else {}
    if kind is K.LOOP:
        kwargs.update(until=lambda r, c: pytest.fail("until ran"), max_iterations=2)
    team = ScriptedTeam({"first": as_member(fail), "later": as_member(forbidden)}, kind, **kwargs)
    with pytest.raises(ValueError) as caught:
        asyncio.run(team.execute(object(), effects))
    assert caught.value is error and effects == ["effect"]


def test_router_calls_selector_once_with_entry_then_passes_selected_allocation():
    root_task, root_context, local_task, materials, result = [object() for _ in range(5)]
    calls = []
    def select(task, context):
        assert task is root_task and context is root_context
        calls.append("select")
        return "b"
    async def selected(task, context):
        assert task is local_task and context["materials"] is materials
        assert context["upstream"] == context["feedback"] == {}
        calls.append("b")
        return result
    async def forbidden(task, context):
        pytest.fail("unselected member ran")
    team = ScriptedTeam({"a": as_member(forbidden), "b": as_member(selected)}, K.ROUTER,
        selector=select, assignments={"a": {"task": None, "context": None},
            "b": {"task": local_task, "context": materials}})
    assert asyncio.run(team.execute(root_task, root_context)) is result
    assert calls == ["select", "b"] and len(team.allocations) == 1


@pytest.mark.parametrize("selection,exc", [("missing", LookupError), (1, TypeError), (None, TypeError)])
def test_router_selection_errors_do_not_execute_members(selection, exc):
    calls = []
    async def member(t, c):
        calls.append(t)
    team = ScriptedTeam({"security": as_member(member), "quick": as_member(member)}, K.ROUTER,
        selector=lambda t, c: selection)
    with pytest.raises(exc) as caught:
        asyncio.run(team.execute(None, None))
    if exc is LookupError:
        assert "missing" in str(caught.value) and "['security', 'quick']" in str(caught.value)
    assert not calls and len(team.allocations) == 1


def test_selector_error_is_not_allocation_error():
    error = RuntimeError("selector")
    def select(t, c):
        raise error
    team = ScriptedTeam({"a": as_member(echo)}, K.ROUTER, selector=select)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(team.execute(None, None))
    assert caught.value is error


@pytest.mark.parametrize("stop_at,limit", [(1, 3), (3, 3), (9, 3)])
def test_loop_whole_rounds_feedback_reset_and_last_round_priority(stop_at, limit):
    root = MappingProxyType({"sentinel": object()})
    rounds, contexts, results = [], [], []
    async def first(task, context):
        assert task == "first assignment"
        assert context["upstream"] == {}
        if results:
            assert context["feedback"]["result"] is results[-1]
        else:
            assert context["feedback"] == {}
        contexts.append(context)
        return {"round": len(results) + 1}
    async def second(task, context):
        assert task == "second assignment"
        assert set(context["upstream"]) == {"first"}
        result = context["upstream"]["first"]
        assert result["round"] == len(results) + 1
        results.append(result)
        contexts.append(context)
        return result
    def until(result, context):
        assert context is root and result is results[-1]
        rounds.append(result)
        return len(rounds) >= stop_at
    team = ScriptedTeam({"first": as_member(first), "second": as_member(second)}, K.LOOP,
        until=until, max_iterations=limit, assignments={
            "first": {"task": "first assignment", "context": None},
            "second": {"task": "second assignment", "context": None}})
    actual = asyncio.run(team.execute("entry", root))
    assert actual is results[-1] and len(results) == min(stop_at, limit)
    assert len(team.allocations) == 1 and len({id(c) for c in contexts}) == 2 * len(results)
    assert set(root) == {"sentinel"}
    exhausted = len(rounds) == limit and len(rounds) < stop_at
    assert exhausted is (stop_at > limit)


@pytest.mark.parametrize("value", [0, 1, None, "yes", [], object()])
def test_until_must_return_actual_bool_after_first_full_round(value):
    calls = []
    async def member(t, c):
        calls.append("member")
        return None
    def until(r, c):
        assert calls == ["member"] and r is None
        return value
    team = ScriptedTeam({"a": as_member(member)}, K.LOOP, until=until, max_iterations=2)
    with pytest.raises(TypeError, match="bool"):
        asyncio.run(team.execute(None, None))
    assert calls == ["member"]


def test_until_exception_is_not_exhaustion_and_none_feedback_is_present():
    error, seen = LookupError("until failed"), []
    async def member(t, c):
        seen.append(c["feedback"])
        return None
    def until(r, c):
        if len(seen) == 2:
            raise error
        return False
    team = ScriptedTeam({"a": as_member(member)}, K.LOOP, until=until, max_iterations=3)
    with pytest.raises(LookupError) as caught:
        asyncio.run(team.execute(None, {}))
    assert caught.value is error and seen == [{}, {"result": None}]


def test_nested_team_keeps_own_mode_and_returns_heterogeneous_business_result():
    tasks, received = [], []
    async def a(t, c):
        tasks.append(t)
        return (1, 2)
    async def b(t, c):
        tasks.append(t)
        assert c["upstream"]["a"] == (1, 2)
        return "report"
    child = ScriptedTeam({"a": as_member(a), "b": as_member(b)}, K.SEQUENTIAL)
    async def final(t, c):
        received.append(c["upstream"]["child"])
        return {"report": received[-1]}
    outer = ScriptedTeam({"child": child, "final": as_member(final)}, K.SEQUENTIAL)
    assert asyncio.run(outer.execute(42, {})) == {"report": "report"}
    assert tasks == [42, 42] and received == ["report"]
    assert len(outer.allocations) == len(child.allocations) == 1
    assert set(child.allocations[0][1]) == {"materials", "upstream", "feedback"}


def test_loop_calls_child_allocation_each_round_without_changing_root():
    root = MappingProxyType({"loop_exhausted": object()})
    child = ScriptedTeam({"leaf": as_member(echo)}, K.PARALLEL)
    outer = ScriptedTeam({"round": child}, K.LOOP, until=lambda r, c: False, max_iterations=3)
    assert asyncio.run(outer.execute("work", root)) == {"leaf": "work"}
    assert len(outer.allocations) == 1 and len(child.allocations) == 3
    assert all(entry[1]["materials"] is root for entry in child.allocations)
    assert child.allocations[0][1]["feedback"] == {}
    assert child.allocations[1][1]["feedback"] == {"result": {"leaf": "work"}}
    assert len(root) == 1


def test_dynamic_artifacts_are_carried_explicitly_without_accumulating_upstream():
    artifact = object()
    async def a(t, c):
        return artifact
    async def b(t, c):
        return {"proposal": c["upstream"]["a"], "notes": "revision"}
    async def c(t, ctx):
        assert set(ctx["upstream"]) == {"b"}
        assert ctx["upstream"]["b"]["proposal"] is artifact
        return ctx["upstream"]["b"]
    team = ScriptedTeam({"a": as_member(a), "b": as_member(b), "c": as_member(c)}, K.SEQUENTIAL)
    assert asyncio.run(team.execute(None, {}))["proposal"] is artifact


def test_nested_loops_keep_their_feedback_local_and_shared_material_untouched():
    root = MappingProxyType({"loop_exhausted": object()})
    seen, inner_decisions = [], []
    async def member(task, context):
        assert context["materials"] is root
        seen.append((dict(context["upstream"]), dict(context["feedback"])))
        return len(seen)
    def inner_until(result, entry):
        inner_decisions.append(entry)
        return False
    child = ScriptedTeam({"leaf": as_member(member)}, K.LOOP, until=inner_until, max_iterations=2,
        assignments={"leaf": {"task": "inner work", "context": root}})
    outer = ScriptedTeam({"round": child}, K.LOOP, until=lambda r, c: False, max_iterations=2)
    assert asyncio.run(outer.execute("outer work", root)) == 4
    assert seen == [({}, {}), ({}, {"result": 1}), ({}, {}), ({}, {"result": 3})]
    assert len(outer.allocations) == 1 and len(child.allocations) == 2
    assert all(c["materials"] is root for c in inner_decisions)
    assert len(root) == 1


@pytest.mark.parametrize("kind", [K.ROUTER, K.LOOP])
def test_synchronous_decision_can_propagate_cancellation(kind):
    def cancel(*args):
        raise asyncio.CancelledError("decision cancelled")
    team = ScriptedTeam({"a": as_member(echo)}, kind,
        **({"selector": cancel} if kind is K.ROUTER else {"until": cancel, "max_iterations": 2}))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(team.execute(None, {}))


@pytest.mark.parametrize("kind", [K.SEQUENTIAL, K.ROUTER, K.LOOP])
def test_external_cancellation_reaches_selected_member_and_stops_later(kind):
    async def scenario():
        started, cancelled = asyncio.Event(), asyncio.Event()
        async def wait(t, c):
            c["materials"].append("effect")
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        async def later(t, c):
            pytest.fail("later/unselected ran")
        kwargs = {"selector": lambda t, c: "first"} if kind is K.ROUTER else {}
        if kind is K.LOOP:
            kwargs.update(until=lambda r, c: pytest.fail("until ran"), max_iterations=2)
        team = ScriptedTeam({"first": as_member(wait), "later": as_member(later)}, kind, **kwargs)
        effects = []
        async with asyncio.timeout(5):
            task = asyncio.create_task(team.execute(None, effects))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert cancelled.is_set() and effects == ["effect"]
    asyncio.run(scenario())
