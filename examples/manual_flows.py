"""Two handwritten sequential baselines using deterministic fake functions.

Business results travel through return values; caller-owned context carries
shared settings and an application-maintained event list. No model is called.
"""

import asyncio
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Analysis:
    summary: str
    evidence: str


@dataclass
class ResearchContext:
    audience: str
    source_name: str
    events: list[str] = field(default_factory=list)


async def fake_analyze(task: str, context: ResearchContext) -> Analysis:
    """Return a scripted finding for the baseline's latency fixture."""
    context.events.append("analyze")
    return Analysis("延迟下降，但仅凭这些资料不能判断原因。", task)


async def fake_write_report(task: Analysis, context: ResearchContext) -> str:
    context.events.append("report")
    return (
        f"面向：{context.audience}\n"
        f"结论：{task.summary}\n"
        f"证据：{task.evidence}（来源：{context.source_name}）"
    )


async def manual_a(task: str, context: ResearchContext) -> str:
    analysis = await fake_analyze(task, context)
    return await fake_write_report(analysis, context)


@dataclass(frozen=True)
class ChangePlan:
    goal: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class ReviewOpinion:
    accepted: bool
    comment: str


@dataclass
class ChangeContext:
    required_step: str
    events: list[str] = field(default_factory=list)


async def fake_plan(task: str, context: ChangeContext) -> ChangePlan:
    """Return scripted steps for the baseline's timeout-change fixture."""
    context.events.append("plan")
    return ChangePlan(task, ("修改超时配置", "补充超时测试"))


async def fake_review(task: ChangePlan, context: ChangeContext) -> ReviewOpinion:
    context.events.append("review")
    accepted = context.required_step in task.steps
    return ReviewOpinion(
        accepted,
        "方案包含要求的测试步骤。" if accepted else "方案缺少要求的测试步骤。",
    )


async def manual_b(task: str, context: ChangeContext) -> ReviewOpinion:
    plan = await fake_plan(task, context)
    return await fake_review(plan, context)


async def main() -> None:
    research_task = "平均延迟从 120 ms 降至 90 ms。"
    research_context = ResearchContext("项目组", "压测记录")
    report = await manual_a(research_task, research_context)
    assert report == (
        "面向：项目组\n"
        "结论：延迟下降，但仅凭这些资料不能判断原因。\n"
        "证据：平均延迟从 120 ms 降至 90 ms。（来源：压测记录）"
    )
    assert research_context.events == ["analyze", "report"]
    print(f"A input: {research_task}")
    print(f"A result:\n{report}")
    print(f"A context.events: {research_context.events}")

    change_task = "将请求超时配置调整为 10 秒。"
    change_context = ChangeContext("补充超时测试")
    review = await manual_b(change_task, change_context)
    assert review == ReviewOpinion(True, "方案包含要求的测试步骤。")
    assert change_context.events == ["plan", "review"]
    print(f"B input: {change_task}")
    print(f"B result: {review}")
    print(f"B context.events: {change_context.events}")
    print("Both handwritten sequential baselines passed.")


if __name__ == "__main__":
    asyncio.run(main())
