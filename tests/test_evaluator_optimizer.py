"""Copyable optimization uses real feedback and preserves manual control semantics."""

import asyncio

import pytest

from examples.composites import evaluator_optimizer as flow
from nooa_patterns import PatternKind


@pytest.mark.parametrize(
    ("required", "limit", "rounds", "accepted"),
    [(("目标",), 3, 1, True), (("目标", "测试", "回滚"), 3, 3, True),
     (("目标", "测试", "回滚"), 2, 2, False)],
    ids=["early", "last-allowed", "exhausted"],
)
def test_manual_and_composed_equivalence_with_fresh_state(required, limit, rounds, accepted) -> None:
    runs = []
    for execute in (flow.manual, flow.composed):
        task, context, generator = flow.Request("发布说明", required), flow.Context(), flow.FakeGenerator()
        sentinel = object()
        context.loop_exhausted = sentinel
        result = asyncio.run(execute(task, context, generator, max_iterations=limit))
        assert result.rounds == rounds and result.accepted is accepted
        assert result.exhausted is (rounds == limit and not accepted)
        assert context.events == ["generate", "evaluate", "feedback"] * rounds
        assert len(generator.calls) == len(context.evaluations) == rounds
        assert generator.calls[0][0] is task
        for index, evaluation in enumerate(context.evaluations):
            request, shared = generator.calls[index]
            assert shared is context and evaluation.draft is generator.results[index]
            assert evaluation.draft.request is request
            if index:
                previous = context.evaluations[index - 1]
                assert request.feedback is previous.missing
                assert request.text == previous.draft.text
        assert result.result.feedback is context.evaluations[-1].missing
        assert result.result.text == context.evaluations[-1].draft.text
        assert context.loop_exhausted is sentinel
        runs.append((result, context, generator))
    left, right = runs
    assert left[0] == right[0] and left[0] is not right[0]
    assert left[1] is not right[1] and left[1].events is not right[1].events
    assert left[1].evaluations == right[1].evaluations
    assert left[2] is not right[2] and left[2].calls[0][0] is not right[2].calls[0][0]


def test_sequential_round_explicitly_closes_the_type_cycle_and_uses_feedback() -> None:
    generator, context = flow.FakeGenerator(), flow.Context()
    task = flow.Request("说明", ("先验证", "再部署"), feedback=("再部署", "先验证"))
    round_team = flow.build_round(generator)
    assert round_team.pattern is PatternKind.SEQUENTIAL
    assert list(round_team.members) == ["generate", "evaluate", "feedback"]
    result = asyncio.run(round_team.execute(task, context))
    assert isinstance(result, flow.Request)
    assert result.text == "再部署"  # Critic-specified order wins over required order.
    assert result.feedback == ("先验证",)
    assert generator.calls[0] == (task, context)


def test_repeated_calls_create_new_observers_without_resetting_business_members() -> None:
    generator, context = flow.FakeGenerator(), flow.Context()
    task = flow.Request("说明", ("验证",))

    async def scenario() -> None:
        first = await flow.composed(task, context, generator, max_iterations=3)
        second = await flow.composed(task, context, generator, max_iterations=3)
        assert first.rounds == second.rounds == 1
        assert first.accepted and second.accepted
        assert not first.exhausted and not second.exhausted

    asyncio.run(scenario())
    assert len(generator.calls) == len(context.evaluations) == 2


@pytest.mark.parametrize("execute", [flow.manual, flow.composed], ids=["manual", "composed"])
def test_evaluation_failure_propagates_without_feedback_or_exhaustion(monkeypatch, execute) -> None:
    failure = ValueError("evaluation unavailable")
    context, generator = flow.Context(), flow.FakeGenerator()

    async def broken(draft, shared):
        assert draft is generator.results[0] and shared is context
        shared.events.append("evaluation:failed")
        raise failure

    monkeypatch.setattr(flow, "evaluate", broken)
    outcome = None
    with pytest.raises(ValueError) as caught:
        outcome = asyncio.run(execute(flow.Request("说明", ("验证",)), context, generator, max_iterations=3))
    assert caught.value is failure and outcome is None
    assert context.events == ["generate", "evaluation:failed"]
    assert len(generator.calls) == 1 and context.evaluations == []


@pytest.mark.parametrize("execute", [flow.manual, flow.composed], ids=["manual", "composed"])
def test_cancellation_stops_evaluation_and_feedback(execute) -> None:
    context = flow.Context()

    async def scenario() -> None:
        started, cleaned = asyncio.Event(), asyncio.Event()

        class WaitingGenerator(flow.FakeGenerator):
            async def execute(self, task, shared):
                self.calls.append((task, shared))
                shared.events.append("generate:start")
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned.set()

        generator = WaitingGenerator()
        async with asyncio.timeout(5):
            running = asyncio.create_task(execute(flow.Request("说明", ("验证",)), context, generator,
                                                  max_iterations=3))
            await started.wait()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
        assert cleaned.is_set() and len(generator.calls) == 1

    asyncio.run(scenario())
    assert context.events == ["generate:start"] and context.evaluations == []
