"""A fake technical review: concurrent analyses, plain aggregation, one route.

The caller explicitly supplies the proposal in application context so the
aggregation bridge can build ReviewRequest. No library injects that field.
Findings and opinions are deterministic fixtures, not real technical advice.
"""

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from nooa_patterns import Parallel, Router, Sequential, Team, TeamMember, as_member

if __package__:
    from . import parallel_review as analysis
else:
    import parallel_review as analysis


@dataclass(kw_only=True)
class ReviewContext(analysis.ReviewContext):
    proposal: analysis.Proposal


@dataclass(frozen=True)
class ReviewRequest:
    proposal: analysis.Proposal
    bundle: analysis.AnalysisBundle


@dataclass(frozen=True)
class ReviewOpinion:
    reviewer: str
    comment: str


class FakeReviewer:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple[ReviewRequest, ReviewContext]] = []
        self.results: list[ReviewOpinion] = []

    async def execute(self, task: ReviewRequest, context: ReviewContext) -> ReviewOpinion:
        self.calls.append((task, context))
        context.events.append(f"review:{self.name}")
        await asyncio.sleep(0)
        result = ReviewOpinion(
            self.name,
            f"示例审查：目标为{task.proposal.goal}，风险等级为{task.bundle.risk.level}。",
        )
        self.results.append(result)
        return result


def make_reviewers() -> dict[str, FakeReviewer]:
    return {name: FakeReviewer(name) for name in ("security", "architecture", "quick")}


async def fake_risk(task: analysis.Proposal, context: ReviewContext) -> analysis.RiskReport:
    report = await analysis.fake_risk(task, context)
    if report.level == "low" and "数据库" in task.text:
        return analysis.RiskReport("medium", "示例数据库变更需要架构审查。")
    return report


def aggregate_request(
    reports: list[analysis.AnalysisReport], context: ReviewContext
) -> ReviewRequest:
    """Plain business aggregation, preserving the supplied proposal and reports."""
    return ReviewRequest(context.proposal, analysis.aggregate(reports))


def select_by_risk(task: ReviewRequest, context: ReviewContext) -> str:
    return {"high": "security", "medium": "architecture", "low": "quick"}[task.bundle.risk.level]


async def manual_review(
    task: analysis.Proposal,
    context: ReviewContext,
    reviewers: Mapping[str, TeamMember],
    selector: Callable[[ReviewRequest, ReviewContext], str] = select_by_risk,
) -> ReviewOpinion:
    jobs = [
        asyncio.create_task(analysis.fake_feasibility(task, context)),
        asyncio.create_task(fake_risk(task, context)),
        asyncio.create_task(analysis.fake_cost(task, context)),
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
    request = aggregate_request(reports, context)
    name = selector(request, context)
    if not isinstance(name, str):
        raise TypeError("selector must return a member name as str")
    if name not in reviewers:
        raise LookupError(f"selector returned {name!r}, available: {list(reviewers)!r}")
    return await reviewers[name].execute(request, context)


def build_review_team(
    reviewers: Mapping[str, TeamMember],
    selector: Callable[[ReviewRequest, ReviewContext], str] = select_by_risk,
) -> Team:
    review = Team(reviewers, Router(selector))
    analyses = Team(
        [as_member(analysis.fake_feasibility), as_member(fake_risk), as_member(analysis.fake_cost)],
        Parallel(),
    )

    async def aggregate_bridge(
        reports: list[analysis.AnalysisReport], context: ReviewContext
    ) -> ReviewRequest:
        return aggregate_request(reports, context)

    return Team([analyses, as_member(aggregate_bridge), review], Sequential())


async def main() -> None:
    for text, expected in (
        ("升级认证组件。", "security"),
        ("修改数据库索引。", "architecture"),
        ("调整日志格式。", "quick"),
    ):
        task = analysis.Proposal(text, "控制变更风险")
        manual_context, composed_context = ReviewContext(proposal=task), ReviewContext(proposal=task)
        manual = await manual_review(task, manual_context, make_reviewers())
        composed = await build_review_team(make_reviewers()).execute(task, composed_context)
        assert manual == composed and composed.reviewer == expected
        assert sorted(manual_context.events) == sorted(composed_context.events)
        print(f"{text} -> {composed.reviewer}: {composed.comment}")
    print("Handwritten and composed routed reviews passed.")


if __name__ == "__main__":
    asyncio.run(main())
