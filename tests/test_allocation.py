"""The real ordinary allocate boundary, isolated from NOOA for fast unit tests."""

import asyncio

import pytest

from nooa_patterns import AllocationError, PatternKind as K, Team, as_member


@pytest.fixture
def allocation(monkeypatch):
    state = {"result": {"a": {"task": None, "context": None}}, "calls": [], "executed": []}
    async def leaf(t, c):
        state["executed"].append((t, c))
        return t
    team = Team({"a": as_member(leaf)}, K.SEQUENTIAL, llm=None)
    monkeypatch.setattr(team, "_describe_members", lambda: {"a": "actual capability"})
    monkeypatch.setattr(team, "_describe_execution", lambda: "execution contract")
    async def generate(**inputs):
        state["calls"].append(inputs)
        if "error" in state:
            raise state["error"]
        return state["result"]
    monkeypatch.setattr(team, "_generate_assignments", generate)
    return team, state


def test_allocate_returns_validated_reference_without_running_members(allocation):
    team, state = allocation
    task, context, materials = object(), object(), object()
    state["result"]["a"] = {"task": task, "context": materials}
    result = asyncio.run(team.allocate(task, context))
    assert result is state["result"] and result["a"]["context"] is materials
    assert state["executed"] == [] and len(state["calls"]) == 1
    inputs = state["calls"][0]
    assert inputs["task"] is task and inputs["context"] is context
    assert inputs["member_descriptions"] == {"a": "actual capability"}
    assert inputs["execution_contract"] == "execution contract"
    assert "sequential" in inputs["pattern_description"]


def test_preview_and_execute_are_independent_generations(allocation):
    team, state = allocation
    state["result"]["a"]["task"] = "preview"
    assert asyncio.run(team.allocate(None, None))["a"]["task"] == "preview"
    state["result"] = {"a": {"task": "actual", "context": None}}
    assert asyncio.run(team.execute(None, None)) == "actual"
    assert len(state["calls"]) == 2 and len(state["executed"]) == 1


@pytest.mark.parametrize("result,cause", [
    ([], TypeError), (None, TypeError), ({}, ValueError),
    ({"other": {"task": 1, "context": 2}}, ValueError),
    ({"a": 1}, TypeError), ({"a": {"task": 1}}, ValueError),
    ({"a": {"task": 1, "context": 2, "extra": 3}}, ValueError),
    ({"a": {"task": 1, "context": 2}, "extra": {}}, ValueError),
])
def test_invalid_allocation_keeps_cause_and_team_and_runs_nobody(allocation, result, cause):
    team, state = allocation
    state["result"] = result
    with pytest.raises(AllocationError) as caught:
        asyncio.run(team.execute(None, None))
    assert caught.value.team is team and isinstance(caught.value.__cause__, cause)
    assert state["executed"] == [] and len(state["calls"]) == 1


@pytest.mark.parametrize("phase", ["members", "execution", "generation"])
def test_allocation_phase_failure_preserves_original_cause(allocation, monkeypatch, phase):
    team, state = allocation
    error = TimeoutError("original failure")
    def fail():
        raise error
    if phase == "members":
        monkeypatch.setattr(team, "_describe_members", fail)
    elif phase == "execution":
        monkeypatch.setattr(team, "_describe_execution", fail)
    else:
        state["error"] = error
    with pytest.raises(AllocationError) as caught:
        asyncio.run(team.allocate(None, None))
    assert caught.value.__cause__ is error and caught.value.team is team
    assert not state["executed"]


def test_allocation_cancellation_is_not_wrapped(allocation, monkeypatch):
    team, state = allocation
    async def scenario():
        started, stopped = asyncio.Event(), asyncio.Event()
        async def generate(**inputs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        monkeypatch.setattr(team, "_generate_assignments", generate)
        async with asyncio.timeout(5):
            running = asyncio.create_task(team.execute(None, None))
            await started.wait()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
        assert stopped.is_set() and not state["executed"]
    asyncio.run(scenario())


def test_outer_timeout_keeps_asyncio_protocol(allocation, monkeypatch):
    team, state = allocation
    async def generate(**inputs):
        await asyncio.Event().wait()
    monkeypatch.setattr(team, "_generate_assignments", generate)
    async def scenario():
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0):
                await team.execute(None, None)
    asyncio.run(scenario())
    assert not state["executed"]


def test_child_allocation_error_is_not_relabelled_as_parent_failure(allocation):
    from conftest import ScriptedTeam
    child, state = allocation
    original = RuntimeError("child generation")
    state["error"] = original
    parent = ScriptedTeam({"child": child}, K.SEQUENTIAL)
    with pytest.raises(AllocationError) as caught:
        asyncio.run(parent.execute(None, None))
    assert caught.value.team is child and caught.value.__cause__ is original
