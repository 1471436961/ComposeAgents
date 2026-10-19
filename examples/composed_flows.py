"""The two baselines composed with Team, Sequential and explicit adaptation."""

import asyncio

from nooa_patterns import Sequential, Team, as_member

if __package__:
    from . import manual_flows as flows
else:
    import manual_flows as flows


async def composed_a(task: str, context: flows.ResearchContext) -> str:
    team = Team(
        members=[as_member(flows.fake_analyze), as_member(flows.fake_write_report)],
        pattern=Sequential(),
    )
    return await team.execute(task, context)


async def composed_b(task: str, context: flows.ChangeContext) -> flows.ReviewOpinion:
    team = Team(
        members=[as_member(flows.fake_plan), as_member(flows.fake_review)],
        pattern=Sequential(),
    )
    return await team.execute(task, context)


async def main() -> None:
    research_task = "平均延迟从 120 ms 降至 90 ms。"
    research_context = flows.ResearchContext("项目组", "压测记录")
    report = await composed_a(research_task, research_context)
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
    change_context = flows.ChangeContext("补充超时测试")
    review = await composed_b(change_task, change_context)
    assert review == flows.ReviewOpinion(True, "方案包含要求的测试步骤。")
    assert change_context.events == ["plan", "review"]
    print(f"B input: {change_task}")
    print(f"B result: {review}")
    print(f"B context.events: {change_context.events}")
    print("Both composed sequential flows passed.")


if __name__ == "__main__":
    asyncio.run(main())
