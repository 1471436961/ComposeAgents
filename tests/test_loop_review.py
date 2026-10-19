"""Business feedback, fresh observations, and aborted calls never reported as exhaustion."""

import asyncio
from collections import Counter

import pytest

from examples import loop_review as flows
from nooa_patterns import Parallel, Router, Sequential


@pytest.mark.parametrize(
    ("text", "limit", "rounds", "accepted", "reviewer"),
    [("调整日志格式，提供回滚开关。", 3, 1, True, "quick"),
     ("升级认证组件。", 2, 2, True, "security"),
     ("修改数据库索引，外部审批未完成。", 3, 3, False, "architecture"),
     ("升级认证组件。", 1, 1, False, "security")],
    ids=["early", "last-allowed", "exhausted", "unreviewed-feedback"],
)
def test_manual_and_composed_feedback_runs_are_equivalent_with_fresh_application_state(
    text: str, limit: int, rounds: int, accepted: bool, reviewer: str
) -> None:
    task = flows.Proposal(text, "保持服务可恢复")
    runs = []
    for execute in (flows.manual_review, flows.composed_review):
        context = flows.ReviewContext(proposal=task)
        reviewers = flows.single.make_reviewers()
        assert context.events == context.reviews == context.proposals == context.feedbacks == []
        result = asyncio.run(execute(task, context, reviewers, max_iterations=limit))

        assert result.rounds == rounds and result.last_ok is accepted
        assert result.exhausted is (rounds == limit and not accepted)
        assert result.result is context.feedbacks[-1]
        assert len(context.proposals) == len(context.reviews) == len(context.feedbacks) == rounds
        assert context.proposals[0] is task
        assert all(context.proposals[i] is context.feedbacks[i - 1] for i in range(1, rounds))
        assert len(reviewers[reviewer].calls) == rounds
        assert all(member.calls == [] for name, member in reviewers.items() if name != reviewer)
        for index, opinion in enumerate(context.reviews):
            request, shared = reviewers[reviewer].calls[index]
            assert opinion.request is request and shared is context
            assert opinion.request.proposal is context.proposals[index]
            assert opinion.review is reviewers[reviewer].results[index]
            events = context.events[index * 6:(index + 1) * 6]
            assert events[0] == "prepare" and events[-2:] == [f"review:{reviewer}", "feedback"]
            assert Counter(events[1:4]) == Counter(["feasibility", "risk", "cost"])
        assert len(context.events) == 6 * rounds
        assert "loop_exhausted" not in vars(context)
        if accepted:
            assert result.result is context.reviews[-1].request.proposal
        if limit == 1:
            assert result.result is not task
            assert context.reviews[-1].request.proposal is task
            assert "回滚开关" in result.result.text and not context.reviews[-1].accepted
        runs.append((result, context, reviewers))

    left, right = runs
    assert left[0] == right[0] and left[0] is not right[0]
    assert left[1] is not right[1] and left[1].events is not right[1].events
    assert left[1].reviews == right[1].reviews
    assert Counter(left[1].events) == Counter(right[1].events)
    assert all(left[2][name] is not right[2][name] for name in left[2])


def test_round_contains_analysis_review_and_explicit_feedback_conversion() -> None:
    task = flows.Proposal("升级认证组件。", "保留回滚能力")
    context, reviewers = flows.ReviewContext(proposal=task), flows.single.make_reviewers()
    stages = flows.build_round(reviewers)
    assert len(stages) == 3
    assert isinstance(stages[0].pattern, Sequential)
    assert isinstance(stages[0].members[1].pattern, Parallel)
    assert isinstance(stages[1].pattern, Router)

    async def scenario() -> None:
        request = await stages[0].execute(task, context)
        assert request.proposal is task
        opinion = await stages[1].execute(request, context)
        assert isinstance(opinion, flows.ReviewOpinion) and not opinion.accepted
        proposal = await stages[2].execute(opinion, context)
        assert isinstance(proposal, flows.Proposal)
        assert proposal is context.feedbacks[-1] and proposal is not task
        next_request = await stages[0].execute(proposal, context)
        assert next_request.proposal is proposal

    asyncio.run(scenario())


def test_application_observation_closure_is_fresh_but_member_history_is_not_reset() -> None:
    task = flows.Proposal("升级认证组件，提供回滚开关。", "安全上线")
    context, reviewers = flows.ReviewContext(proposal=task), flows.single.make_reviewers()

    async def scenario() -> None:
        first = await flows.composed_review(task, context, reviewers, max_iterations=3)
        second = await flows.composed_review(task, context, reviewers, max_iterations=3)
        assert first.rounds == second.rounds == 1
        assert first.last_ok and second.last_ok
        assert not first.exhausted and not second.exhausted

    asyncio.run(scenario())
    assert len(context.reviews) == len(reviewers["security"].calls) == 2
    assert "loop_exhausted" not in vars(context)


@pytest.mark.parametrize("execute", [flows.manual_review, flows.composed_review], ids=["manual", "team"])
def test_failed_review_propagates_without_feedback_or_an_exhaustion_outcome(execute) -> None:
    failure = ValueError("review service failed")
    task = flows.Proposal("升级认证组件。", "控制风险")
    context = flows.ReviewContext(proposal=task)
    sentinel = object()
    context.loop_exhausted = sentinel  # Caller-owned pre-existing field.

    class Broken(flows.single.FakeReviewer):
        async def execute(self, request, shared):
            self.calls.append((request, shared))
            raise failure

    reviewers = flows.single.make_reviewers()
    reviewers["security"] = Broken("security")
    outcome = None
    with pytest.raises(ValueError) as caught:
        outcome = asyncio.run(execute(task, context, reviewers, max_iterations=2))
    assert caught.value is failure and outcome is None
    assert context.loop_exhausted is sentinel
    assert len(context.proposals) == len(reviewers["security"].calls) == 1
    assert context.feedbacks == context.reviews == []


@pytest.mark.parametrize("execute", [flows.manual_review, flows.composed_review], ids=["manual", "team"])
def test_cancelled_review_does_not_produce_an_exhaustion_outcome(execute) -> None:
    task = flows.Proposal("升级认证组件。", "控制风险")
    context = flows.ReviewContext(proposal=task)
    sentinel = object()
    context.loop_exhausted = sentinel

    async def scenario() -> None:
        started, cleaned = asyncio.Event(), asyncio.Event()

        class Waiting(flows.single.FakeReviewer):
            async def execute(self, request, shared):
                self.calls.append((request, shared))
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned.set()

        reviewers = flows.single.make_reviewers()
        reviewers["security"] = Waiting("security")
        outcome = None
        async with asyncio.timeout(5):
            running = asyncio.create_task(execute(task, context, reviewers, max_iterations=2))
            await started.wait()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                outcome = await running
        assert outcome is None and cleaned.is_set()
        assert len(reviewers["security"].calls) == 1

    asyncio.run(scenario())
    assert context.loop_exhausted is sentinel and context.feedbacks == context.reviews == []
