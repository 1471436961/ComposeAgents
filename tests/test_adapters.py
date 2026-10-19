"""Callable bridging behavior without a NOOA runtime or real model."""

import asyncio
import inspect

import pytest

from nooa_patterns.adapters import as_member


def test_adapter_exposes_a_real_async_execute_method_on_its_class() -> None:
    async def operation(task: object, context: object) -> object:
        return task

    member = as_member(operation)
    execute = inspect.getattr_static(type(member), "execute")

    assert inspect.isfunction(execute)
    assert inspect.iscoroutinefunction(execute)


def test_async_function_keeps_argument_and_result_references() -> None:
    task = object()
    context: dict[str, list[str]] = {"events": []}
    expected_result: list[str] = ["business result"]

    async def operation(value: object, shared: dict[str, list[str]]) -> list[str]:
        assert value is task
        assert shared is context
        shared["events"].append("called")
        return expected_result

    result = asyncio.run(as_member(operation).execute(task, context))

    assert result is expected_result
    assert context == {"events": ["called"]}


def test_bound_method_keeps_original_instance_state_between_calls() -> None:
    class Worker:
        def __init__(self) -> None:
            self.calls = 0

        async def work(self, task: int, context: list[int]) -> int:
            self.calls += 1
            context.append(self.calls)
            return task + self.calls

    worker = Worker()
    member = as_member(worker.work)
    context: list[int] = []

    async def scenario() -> None:
        assert await member.execute(10, context) == 11
        assert await member.execute(10, context) == 12

    asyncio.run(scenario())

    assert worker.calls == 2
    assert context == [1, 2]


def test_explicit_bridge_maps_a_different_signature() -> None:
    class Writer:
        def __init__(self) -> None:
            self.context = object()
            self.received: list[str] = []

        async def draft(self, *, prompt: str) -> str:
            self.received.append(prompt)
            return f"draft: {prompt}"

    writer = Writer()
    native_context = writer.context
    shared_context = {"prefix": "review "}

    async def bridge(task: str, context: dict[str, str]) -> str:
        return await writer.draft(prompt=context["prefix"] + task)

    result = asyncio.run(as_member(bridge).execute("change", shared_context))

    assert result == "draft: review change"
    assert writer.received == ["review change"]
    assert writer.context is native_context
    assert shared_context == {"prefix": "review "}


def test_exception_is_not_wrapped_or_retried_and_effects_remain() -> None:
    failure = ValueError("planned failure")
    context: list[str] = []

    async def fail(task: object, shared: list[str]) -> object:
        shared.append("effect before failure")
        raise failure

    with pytest.raises(ValueError) as caught:
        asyncio.run(as_member(fail).execute(object(), context))

    assert caught.value is failure
    assert context == ["effect before failure"]


def test_none_arguments_and_result_are_not_special_values() -> None:
    calls: list[tuple[object, object]] = []

    async def operation(task: None, context: None) -> None:
        calls.append((task, context))
        return None

    result = asyncio.run(as_member(operation).execute(None, None))

    assert result is None
    assert calls == [(None, None)]


def test_cancellation_propagates_and_preserves_existing_effects() -> None:
    context: list[str] = []

    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def operation(task: object, shared: list[str]) -> object:
            shared.append("started")
            started.set()
            await release.wait()
            shared.append("completed")
            return task

        async with asyncio.timeout(5):
            running = asyncio.create_task(as_member(operation).execute(object(), context))
            await started.wait()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running

    asyncio.run(scenario())

    assert context == ["started"]
