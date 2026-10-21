"""Two business baselines with named tasks and local input bridges.

The example Team overrides allocate with scripted fixtures, so this demo never
calls a model. Production Team.allocate uses native NOOA generation instead.
"""

import asyncio

from nooa_patterns import PatternKind, Team, as_member

if __package__:
    from . import manual_flows as flows
else:
    import manual_flows as flows


class _Pipeline(Team):
    async def allocate(self, task, context):
        first, second = self.members
        return {
            first: {"task": f"Perform {first}", "context": {"input": task, "application": context}},
            second: {"task": f"Perform {second} using the predecessor's result", "context": context},
        }


def build_pipeline(first_name, first_fn, second_name, second_fn):
    async def first(task, context):
        """Process the explicitly allocated input material."""
        return await first_fn(context["materials"]["input"], context["materials"]["application"])
    async def second(task, context):
        """Use the actual direct predecessor's business result."""
        return await second_fn(context["upstream"][first_name], context["materials"])
    return _Pipeline({first_name: as_member(first), second_name: as_member(second)},
        PatternKind.SEQUENTIAL, llm=None)


async def composed_a(task: str, context: flows.ResearchContext) -> str:
    return await build_pipeline("analyze", flows.fake_analyze, "report", flows.fake_write_report).execute(task, context)


async def composed_b(task: str, context: flows.ChangeContext) -> flows.ReviewOpinion:
    return await build_pipeline("plan", flows.fake_plan, "review", flows.fake_review).execute(task, context)


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
