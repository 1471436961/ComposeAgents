"""Three independent analyses, with handwritten and Team-based coordination.

All findings are deterministic fake fixtures, not real technical judgments.
The example stops at AnalysisBundle; no routing or review loop is implemented.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Literal

from nooa_patterns import Parallel, Team, as_member


@dataclass(frozen=True)
class Proposal:
    text: str
    goal: str


@dataclass(frozen=True)
class FeasibilityReport:
    feasible: bool
    note: str


@dataclass(frozen=True)
class RiskReport:
    level: Literal["low", "medium", "high"]
    note: str


@dataclass(frozen=True)
class CostReport:
    engineer_days: int


AnalysisReport = FeasibilityReport | RiskReport | CostReport


@dataclass(frozen=True)
class AnalysisBundle:
    feasibility: FeasibilityReport
    risk: RiskReport
    cost: CostReport


@dataclass
class ReviewContext:
    events: list[str] = field(default_factory=list)


async def fake_feasibility(task: Proposal, context: ReviewContext) -> FeasibilityReport:
    context.events.append("feasibility")
    await asyncio.sleep(0)
    return FeasibilityReport(True, f"示例方案可分步验证目标：{task.goal}")


async def fake_risk(task: Proposal, context: ReviewContext) -> RiskReport:
    context.events.append("risk")
    await asyncio.sleep(0)
    if "认证" in task.text:
        return RiskReport("high", "示例方案涉及认证，需要专门核查。")
    return RiskReport("low", "示例未包含认证变更。")


async def fake_cost(task: Proposal, context: ReviewContext) -> CostReport:
    context.events.append("cost")
    await asyncio.sleep(0)
    return CostReport(2 + len(task.text) // 20)


def aggregate(reports: list[AnalysisReport]) -> AnalysisBundle:
    """Business-level positional validation and aggregation, not a Pattern."""
    if len(reports) != 3:
        raise ValueError("Expected feasibility, risk and cost reports")
    feasibility, risk, cost = reports
    if not (
        isinstance(feasibility, FeasibilityReport)
        and isinstance(risk, RiskReport)
        and isinstance(cost, CostReport)
    ):
        raise TypeError("Reports must be in feasibility, risk, cost order")
    return AnalysisBundle(feasibility, risk, cost)


async def manual_analyze(task: Proposal, context: ReviewContext) -> list[AnalysisReport]:
    jobs = [
        asyncio.create_task(fake_feasibility(task, context)),
        asyncio.create_task(fake_risk(task, context)),
        asyncio.create_task(fake_cost(task, context)),
    ]
    collected = asyncio.gather(*jobs)
    try:
        return await asyncio.shield(collected)
    except BaseException:
        for job in jobs:
            if not job.done():
                job.cancel()
        await asyncio.gather(collected, *jobs, return_exceptions=True)
        raise


def build_analysis_team() -> Team:
    return Team(
        members=[as_member(fake_feasibility), as_member(fake_risk), as_member(fake_cost)],
        pattern=Parallel(),
    )


async def composed_analyze(task: Proposal, context: ReviewContext) -> list[AnalysisReport]:
    return await build_analysis_team().execute(task, context)


async def main() -> None:
    task = Proposal("升级认证组件并保留回滚开关。", "降低认证故障风险")
    manual_context, composed_context = ReviewContext(), ReviewContext()
    manual = await manual_analyze(task, manual_context)
    composed = await composed_analyze(task, composed_context)
    assert manual == composed
    assert aggregate(manual) == aggregate(composed)
    assert sorted(manual_context.events) == sorted(composed_context.events) == [
        "cost", "feasibility", "risk"
    ]
    print(f"Input: {task}")
    print(f"Ordered reports: {[type(report).__name__ for report in composed]}")
    print(f"AnalysisBundle: {aggregate(composed)}")
    print("Handwritten and composed concurrent analyses passed.")


if __name__ == "__main__":
    asyncio.run(main())
