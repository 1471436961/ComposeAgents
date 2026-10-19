"""Bounded fake technical reviews with explicit business feedback.

跨轮类型兼容由应用负责，库不提供 feedback_adapter，也不自动转换：
1. 推荐把反馈转换成员放在 members 末尾；本例用 ReviewOpinion -> Proposal。
2. 入口成员接受多种输入类型，并自行判断处理。
3. 应用在 Loop 外包装显式转换；要逐轮转换，包装须参与每轮调用，
   不能只在整次执行结束后转换一次。

Exhaustion is observed with a new until closure per run, never by a library
context field or callback. A final rejected round may return a converted
proposal that has not been reviewed yet. All judgments are fake fixtures.
"""

import asyncio
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from nooa_patterns import Loop, Parallel, Router, Sequential, Team, TeamMember, as_member

if __package__:
    from . import router_review as single
else:
    import router_review as single

Proposal = single.analysis.Proposal


@dataclass(frozen=True)
class ReviewOpinion:
    request: single.ReviewRequest
    review: single.ReviewOpinion
    accepted: bool


@dataclass(kw_only=True)
class ReviewContext(single.ReviewContext):
    reviews: list[ReviewOpinion] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    feedbacks: list[Proposal] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewRun:
    """Application observation only; not a Loop return wrapper or library API."""

    result: Proposal
    rounds: int
    last_ok: bool
    exhausted: bool


async def prepare_proposal(task: Proposal, context: ReviewContext) -> Proposal:
    # An explicit business member updates the application's current proposal.
    context.proposal = task
    context.proposals.append(task)
    context.events.append("prepare")
    return task


async def aggregate_bridge(
    reports: list[single.analysis.AnalysisReport], context: ReviewContext
) -> single.ReviewRequest:
    return single.aggregate_request(reports, context)


async def review_request(
    request: single.ReviewRequest, context: ReviewContext, reviewer: single.FakeReviewer
) -> ReviewOpinion:
    review = await reviewer.execute(request, context)
    accepted = "回滚开关" in request.proposal.text and "外部审批未完成" not in request.proposal.text
    opinion = ReviewOpinion(request, review, accepted)
    context.reviews.append(opinion)  # Business history belongs to this application.
    return opinion


async def feedback_to_proposal(opinion: ReviewOpinion, context: ReviewContext) -> Proposal:
    proposal = opinion.request.proposal
    if not opinion.accepted and "回滚开关" not in proposal.text:
        proposal = Proposal(f"{proposal.text} 补充回滚开关。", proposal.goal)
    context.feedbacks.append(proposal)
    context.events.append("feedback")
    return proposal


def review_passed(result: Proposal, context: ReviewContext) -> bool:
    """A pure synchronous decision reading the application's last review."""
    return context.reviews[-1].accepted


def reviewer_member(reviewer: single.FakeReviewer) -> TeamMember:
    async def execute(request: single.ReviewRequest, context: ReviewContext) -> ReviewOpinion:
        return await review_request(request, context, reviewer)

    return as_member(execute)


def build_round(reviewers: Mapping[str, single.FakeReviewer]) -> list[TeamMember]:
    analyses = Team(
        [as_member(single.analysis.fake_feasibility), as_member(single.fake_risk),
         as_member(single.analysis.fake_cost)], Parallel(),
    )
    analysis_stage = Team(
        [as_member(prepare_proposal), analyses, as_member(aggregate_bridge)], Sequential()
    )
    review_stage = Team(
        {name: reviewer_member(reviewer) for name, reviewer in reviewers.items()},
        Router(single.select_by_risk),
    )
    return [analysis_stage, review_stage, as_member(feedback_to_proposal)]


async def composed_review(
    task: Proposal,
    context: ReviewContext,
    reviewers: Mapping[str, single.FakeReviewer],
    *,
    max_iterations: int,
) -> ReviewRun:
    rounds, last_ok = 0, False

    def until(result: Proposal, shared: ReviewContext) -> bool:
        nonlocal rounds, last_ok
        rounds += 1
        last_ok = review_passed(result, shared)
        return last_ok

    # A new observation closure is created on every application call.
    team = Team(build_round(reviewers), Loop(until, max_iterations=max_iterations))
    result = await team.execute(task, context)
    # Errors/cancellation propagate and never execute this normal-return code.
    exhausted = rounds == max_iterations and not last_ok
    return ReviewRun(result, rounds, last_ok, exhausted)


async def manual_review(
    task: Proposal,
    context: ReviewContext,
    reviewers: Mapping[str, single.FakeReviewer],
    *,
    max_iterations: int,
) -> ReviewRun:
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int):
        raise TypeError("max_iterations must be an int, not bool")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    current, rounds, last_ok = task, 0, False
    for _ in range(max_iterations):
        current = await prepare_proposal(current, context)
        jobs = [
            asyncio.create_task(single.analysis.fake_feasibility(current, context)),
            asyncio.create_task(single.fake_risk(current, context)),
            asyncio.create_task(single.analysis.fake_cost(current, context)),
        ]
        collected = asyncio.gather(*jobs)
        try:
            reports = await asyncio.shield(collected)
        except BaseException:
            for job in jobs:
                if not job.done():
                    job.cancel()
            await asyncio.gather(collected, *jobs, return_exceptions=True)
            raise
        request = await aggregate_bridge(reports, context)
        name = single.select_by_risk(request, context)
        opinion = await review_request(request, context, reviewers[name])
        current = await feedback_to_proposal(opinion, context)
        rounds += 1
        last_ok = review_passed(current, context)
        if last_ok:
            break
    exhausted = rounds == max_iterations and not last_ok
    return ReviewRun(current, rounds, last_ok, exhausted)


async def main() -> None:
    for label, text, limit, expected_rounds, expected_ok in (
        ("early", "调整日志格式，提供回滚开关。", 3, 1, True),
        ("last-allowed", "升级认证组件。", 2, 2, True),
        ("exhausted", "修改数据库索引，外部审批未完成。", 3, 3, False),
    ):
        task = Proposal(text, "控制变更风险")
        manual_context, composed_context = ReviewContext(proposal=task), ReviewContext(proposal=task)
        manual = await manual_review(task, manual_context, single.make_reviewers(), max_iterations=limit)
        composed = await composed_review(task, composed_context, single.make_reviewers(), max_iterations=limit)
        assert manual == composed
        assert composed.rounds == expected_rounds and composed.last_ok is expected_ok
        assert composed.exhausted is (expected_rounds == limit and not expected_ok)
        assert manual_context.reviews == composed_context.reviews
        assert Counter(manual_context.events) == Counter(composed_context.events)
        print(f"{label}: rounds={composed.rounds}, last_ok={composed.last_ok}, exhausted={composed.exhausted}")
    print("Handwritten and composed bounded review loops passed.")


if __name__ == "__main__":
    asyncio.run(main())
