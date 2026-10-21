"""Concurrent fan-in, failure identity and cancellation waiting chains."""

import asyncio

import pytest

from nooa_patterns import AllocationError, PatternKind as K, as_member
from conftest import ScriptedTeam


def test_different_assignments_overlap_and_results_keep_named_order_and_identity():
    async def scenario():
        ready, release, finished = [[asyncio.Event() for _ in range(3)] for _ in range(3)]
        tasks, materials, results = [object() for _ in range(3)], [object() for _ in range(3)], [None, {"nested": []}, object()]
        contexts, completion = [], []
        def member(i):
            async def execute(task, context):
                assert task is tasks[i] and context["materials"] is materials[i]
                assert context["upstream"] == context["feedback"] == {}
                contexts.append(context)
                ready[i].set()
                await release[i].wait()
                completion.append(i)
                finished[i].set()
                return results[i]
            return as_member(execute)
        team = ScriptedTeam({str(i): member(i) for i in range(3)}, K.PARALLEL,
            assignments={str(i): {"task": tasks[i], "context": materials[i]} for i in range(3)})
        async with asyncio.timeout(5):
            running = asyncio.create_task(team.execute(None, {}))
            await asyncio.gather(*(e.wait() for e in ready))
            assert not running.done()
            for i in (2, 1, 0):
                release[i].set()
                await finished[i].wait()
            result = await running
        assert list(result) == ["0", "1", "2"]
        assert all(result[str(i)] is results[i] for i in range(3))
        assert completion == [2, 1, 0] and len({id(c) for c in contexts}) == 3
        assert len(team.allocations) == 1
    asyncio.run(scenario())


@pytest.mark.parametrize("trigger", ["failure", "outer-cancel", "member-cancel"])
@pytest.mark.parametrize("nested", [False, True])
def test_failure_or_cancel_reaches_siblings_and_waits_for_nested_cleanup(trigger, nested):
    async def scenario():
        ready = [asyncio.Event(), asyncio.Event()]
        cancelled = [asyncio.Event(), asyncio.Event()]
        cleanup_release = asyncio.Event()
        cleaned, children, effects = [], [], []
        error = ValueError("original business error")
        def waiting(i):
            async def execute(t, c):
                children.append(asyncio.current_task())
                c["materials"].append(i)
                ready[i].set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled[i].set()
                    raise
                finally:
                    await cleanup_release.wait()
                    cleaned.append(i)
            return as_member(execute)
        async def fail(t, c):
            await asyncio.gather(*(e.wait() for e in ready))
            if trigger == "member-cancel":
                raise asyncio.CancelledError("member cancellation")
            if trigger == "failure":
                raise error
            await asyncio.Event().wait()
        branch = {"wait0": waiting(0), "trigger": as_member(fail)}
        if nested:
            child = ScriptedTeam(branch, K.PARALLEL)
            # Deliberately choose the original shared material for the child.
            child.assignments = {n: {"task": None, "context": effects} for n in branch}
            members = {"child": child, "wait1": waiting(1)}
        else:
            members = {**branch, "wait1": waiting(1)}
        team = ScriptedTeam(members, K.PARALLEL)
        async with asyncio.timeout(5):
            running = asyncio.create_task(team.execute(None, effects))
            if trigger == "outer-cancel":
                await asyncio.gather(*(e.wait() for e in ready))
                running.cancel()
            if nested and trigger != "outer-cancel":
                # A parent observes the child's failure only after that child
                # finishes its own cleanup. It cannot cancel outer peers early.
                await cancelled[0].wait()
                assert not cancelled[1].is_set()
                assert not running.done() and cleaned == []
                cleanup_release.set()
                await cancelled[1].wait()
            else:
                await asyncio.gather(*(e.wait() for e in cancelled))
                assert not running.done() and cleaned == []
                cleanup_release.set()
            expected = ValueError if trigger == "failure" else asyncio.CancelledError
            with pytest.raises(expected) as caught:
                await running
            if trigger == "failure":
                assert caught.value is error
        assert sorted(cleaned) == [0, 1] and sorted(effects) == [0, 1]
        assert all(c.done() for c in children)
    asyncio.run(scenario())


@pytest.mark.parametrize("outer_cancel", [False, True])
def test_cleanup_errors_do_not_replace_trigger(outer_cancel):
    async def scenario():
        ready, cleaned = asyncio.Event(), asyncio.Event()
        error = ValueError("business")
        async def waiting(t, c):
            ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
                raise RuntimeError("cleanup")
        async def fail(t, c):
            await ready.wait()
            if outer_cancel:
                await asyncio.Event().wait()
            raise error
        team = ScriptedTeam({"wait": as_member(waiting), "fail": as_member(fail)}, K.PARALLEL)
        async with asyncio.timeout(5):
            running = asyncio.create_task(team.execute(None, None))
            if outer_cancel:
                await ready.wait()
                running.cancel()
            with pytest.raises(asyncio.CancelledError if outer_cancel else ValueError) as caught:
                await running
            if not outer_cancel:
                assert caught.value is error
        assert cleaned.is_set()
    asyncio.run(scenario())


def test_second_external_cancellation_can_interrupt_failure_cleanup():
    async def scenario():
        started, cleanup, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def waiting(t, c):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned.set()
        async def fail(t, c):
            await started.wait()
            raise ValueError("first failure")
        async with asyncio.timeout(5):
            team = ScriptedTeam({"wait": as_member(waiting), "fail": as_member(fail)}, K.PARALLEL)
            running = asyncio.create_task(team.execute(None, None))
            await cleanup.wait()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
        assert cleaned.is_set()
    asyncio.run(scenario())


def test_simultaneous_failures_do_not_make_exception_group():
    async def scenario():
        ready, release = [asyncio.Event(), asyncio.Event()], asyncio.Event()
        errors = [ValueError("a"), ValueError("b")]
        def fail(i):
            async def execute(t, c):
                ready[i].set()
                await release.wait()
                raise errors[i]
            return as_member(execute)
        async with asyncio.timeout(5):
            team = ScriptedTeam({"a": fail(0), "b": fail(1)}, K.PARALLEL)
            running = asyncio.create_task(team.execute(None, None))
            await asyncio.gather(*(e.wait() for e in ready))
            release.set()
            with pytest.raises(ValueError) as caught:
                await running
        assert any(caught.value is e for e in errors)
    asyncio.run(scenario())


def test_suppressed_cancellation_does_not_make_run_successful():
    async def scenario():
        ready, returned = asyncio.Event(), []
        async def suppress(t, c):
            ready.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                returned.append("effect")
                return "ignored result"
        async with asyncio.timeout(5):
            team = ScriptedTeam({"one": as_member(suppress)}, K.PARALLEL)
            running = asyncio.create_task(team.execute(None, None))
            await ready.wait()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
        assert returned == ["effect"]
    asyncio.run(scenario())


def test_failed_team_does_not_cancel_an_independent_teams_work():
    async def scenario():
        ready, release = asyncio.Event(), asyncio.Event()
        async def wait(t, c):
            ready.set()
            await release.wait()
            return t
        error = RuntimeError("other team")
        async def fail(t, c):
            raise error
        first = ScriptedTeam({"a": as_member(wait)}, K.PARALLEL)
        second = ScriptedTeam({"b": as_member(fail)}, K.PARALLEL)
        value = object()
        async with asyncio.timeout(5):
            running = asyncio.create_task(first.execute(value, None))
            await ready.wait()
            with pytest.raises(RuntimeError) as caught:
                await second.execute(None, None)
            assert caught.value is error and not running.done()
            release.set()
            assert (await running)["a"] is value
        assert len(first.allocations) == len(second.allocations) == 1
    asyncio.run(scenario())


def test_completed_sibling_is_not_cancelled_when_other_sibling_fails():
    async def scenario():
        done, children, effects = asyncio.Event(), [], []
        async def completed(t, c):
            children.append(asyncio.current_task())
            effects.append("finished")
            done.set()
            return None
        async def fail(t, c):
            await done.wait()
            raise ValueError("late failure")
        team = ScriptedTeam({"done": as_member(completed), "fail": as_member(fail)}, K.PARALLEL)
        with pytest.raises(ValueError):
            await team.execute(None, None)
        assert children[0].done() and not children[0].cancelled() and effects == ["finished"]
    asyncio.run(scenario())


def test_child_allocation_failure_keeps_origin_and_cancels_peer():
    async def scenario():
        started, cancelled = asyncio.Event(), asyncio.Event()
        child = ScriptedTeam({"unused": as_member(lambda t, c: None)}, K.SEQUENTIAL)
        error = AllocationError("child allocator", team=child)
        async def allocate(t, c):
            await started.wait()
            raise error
        child.allocate = allocate
        async def wait(t, c):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        team = ScriptedTeam({"child": child, "peer": as_member(wait)}, K.PARALLEL)
        with pytest.raises(AllocationError) as caught:
            await team.execute(None, None)
        assert caught.value is error and caught.value.team is child and cancelled.is_set()
    asyncio.run(scenario())
