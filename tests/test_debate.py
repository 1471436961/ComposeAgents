"""Debate has actual cross-round exchange and equivalent concurrent cleanup."""

import asyncio
from collections import Counter

import pytest

from examples.composites import debate as flow


@pytest.mark.parametrize(
    ("limit", "responds", "rounds", "accepted"),
    [(3, True, 2, True), (2, True, 2, True), (3, False, 3, False), (1, True, 1, False)],
    ids=["early", "last-allowed", "exhausted", "first-round-no-responses"],
)
def test_manual_and_composed_exchange_with_fresh_state(limit, responds, rounds, accepted) -> None:
    runs = []
    for execute in (flow.manual, flow.composed):
        task, context, advocates = flow.State("读取缓存"), flow.Context(), flow.make_advocates(responds=responds)
        result = asyncio.run(execute(task, context, advocates, max_iterations=limit))
        assert result.rounds == rounds and result.accepted is accepted
        assert result.exhausted is (rounds == limit and not accepted)
        assert result.result is context.judgments[-1]
        assert len(context.judgments) == rounds
        for index, judgment in enumerate(context.judgments):
            source = task if index == 0 else context.judgments[index - 1]
            for position, advocate in enumerate(advocates):
                argument = judgment.arguments[position]
                assert argument is advocate.results[index]
                assert argument.source is source and advocate.calls[index][0] is source
                assert advocate.calls[index][1] is context
                assert argument.judge_feedback is source.feedback
                expected = tuple(a.claim for a in source.arguments if a.speaker != advocate.name)
                assert argument.replies == (expected if advocate.responds else ())
            if index:
                assert source.feedback and judgment.arguments[0].replies
            events = context.events[index * 3:(index + 1) * 3]
            assert Counter(events[:2]) == Counter(["propose:performance", "propose:reliability"])
            assert events[-1] == "adjudicate"
        assert "loop_exhausted" not in vars(context)
        runs.append((result, context, advocates))
    left, right = runs
    assert left[0] == right[0] and left[0] is not right[0]
    assert left[1] is not right[1] and left[1].events is not right[1].events
    assert left[1].judgments == right[1].judgments
    assert all(a is not b for a, b in zip(left[2], right[2]))
    assert left[2][0].calls[0][0] is not right[2][0].calls[0][0]


@pytest.mark.parametrize("execute", [flow.manual, flow.composed], ids=["manual", "composed"])
def test_proposals_overlap_and_the_judge_receives_member_order(execute) -> None:
    context = flow.Context()

    async def scenario() -> None:
        first_started, second_done, release_first = asyncio.Event(), asyncio.Event(), asyncio.Event()

        class First(flow.FakeAdvocate):
            async def execute(self, task, shared):
                first_started.set()
                await release_first.wait()
                return await super().execute(task, shared)

        class Second(flow.FakeAdvocate):
            async def execute(self, task, shared):
                await first_started.wait()
                argument = await super().execute(task, shared)
                second_done.set()
                return argument

        advocates = [First("first", "低延迟"), Second("second", "高可靠")]
        async with asyncio.timeout(5):
            running = asyncio.create_task(execute(flow.State("缓存"), context, advocates, max_iterations=1))
            await second_done.wait()
            assert not running.done() and context.judgments == []
            release_first.set()
            result = await running
        assert [a.speaker for a in result.result.arguments] == ["first", "second"]
        assert context.events == ["propose:second", "propose:first", "adjudicate"]

    asyncio.run(scenario())


@pytest.mark.parametrize("execute", [flow.manual, flow.composed], ids=["manual", "composed"])
def test_failed_proposal_cancels_peer_and_waits_for_cleanup(execute) -> None:
    context, failure = flow.Context(), ValueError("proposal failed")

    async def scenario() -> None:
        started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

        class Peer(flow.FakeAdvocate):
            async def execute(self, task, shared):
                self.calls.append((task, shared))
                shared.events.append("peer:start")
                started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cleaning.set()
                    await release.wait()
                    shared.events.append("peer:cleaned")
                    raise

        class Broken(flow.FakeAdvocate):
            async def execute(self, task, shared):
                self.calls.append((task, shared))
                await started.wait()
                raise failure

        advocates = [Peer("peer", "可靠"), Broken("broken", "性能")]
        async with asyncio.timeout(5):
            running = asyncio.create_task(execute(flow.State("缓存"), context, advocates, max_iterations=3))
            await cleaning.wait()
            assert not running.done() and context.judgments == []
            release.set()
            with pytest.raises(ValueError) as caught:
                await running
        assert caught.value is failure
        assert all(len(a.calls) == 1 and a.results == [] for a in advocates)

    asyncio.run(scenario())
    assert context.events == ["peer:start", "peer:cleaned"] and context.judgments == []


@pytest.mark.parametrize("execute", [flow.manual, flow.composed], ids=["manual", "composed"])
def test_outer_cancellation_cancels_both_proposers_without_judging(execute) -> None:
    context = flow.Context()

    async def scenario() -> None:
        started = [asyncio.Event(), asyncio.Event()]
        cleaned = [asyncio.Event(), asyncio.Event()]

        class Waiting(flow.FakeAdvocate):
            def __init__(self, index):
                super().__init__(f"speaker-{index}", "论点")
                self.index = index

            async def execute(self, task, shared):
                self.calls.append((task, shared))
                started[self.index].set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned[self.index].set()

        advocates = [Waiting(0), Waiting(1)]
        async with asyncio.timeout(5):
            running = asyncio.create_task(execute(flow.State("缓存"), context, advocates, max_iterations=3))
            await asyncio.gather(*(event.wait() for event in started))
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
        assert all(event.is_set() for event in cleaned)
        assert all(len(a.calls) == 1 for a in advocates)

    asyncio.run(scenario())
    assert context.judgments == [] and context.events == []


@pytest.mark.parametrize("execute", [flow.manual, flow.composed], ids=["manual", "composed"])
def test_judge_failure_propagates_without_starting_a_new_round(monkeypatch, execute) -> None:
    context, advocates = flow.Context(), flow.make_advocates()
    failure = ValueError("judge unavailable")

    async def broken(arguments, shared):
        assert shared is context
        assert all(argument is advocate.results[0] for argument, advocate in zip(arguments, advocates))
        raise failure

    monkeypatch.setattr(flow, "adjudicate", broken)
    outcome = None
    with pytest.raises(ValueError) as caught:
        outcome = asyncio.run(execute(flow.State("缓存"), context, advocates, max_iterations=3))
    assert caught.value is failure and outcome is None
    assert all(len(a.calls) == 1 for a in advocates)
    assert context.judgments == [] and len(context.events) == 2
