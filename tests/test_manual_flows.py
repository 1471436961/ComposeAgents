"""Behavioral baselines before introducing any composition implementation."""

import asyncio

import pytest

from examples import manual_flows as flows


def test_research_flow_handoffs_and_shared_context(monkeypatch: pytest.MonkeyPatch) -> None:
    task = "平均延迟从 120 ms 降至 90 ms。"
    context = flows.ResearchContext("项目组", "压测记录")
    calls: list[tuple[object, object]] = []
    analyses: list[flows.Analysis] = []
    reports: list[str] = []
    original_analyze = flows.fake_analyze
    original_write_report = flows.fake_write_report

    async def observe_analyze(value: str, shared: flows.ResearchContext) -> flows.Analysis:
        calls.append((value, shared))
        result = await original_analyze(value, shared)
        analyses.append(result)
        return result

    async def observe_report(value: flows.Analysis, shared: flows.ResearchContext) -> str:
        calls.append((value, shared))
        assert shared.events == ["analyze"]
        result = await original_write_report(value, shared)
        reports.append(result)
        return result

    monkeypatch.setattr(flows, "fake_analyze", observe_analyze)
    monkeypatch.setattr(flows, "fake_write_report", observe_report)

    result = asyncio.run(flows.manual_a(task, context))

    assert len(calls) == 2
    assert calls[0][0] is task
    assert calls[1][0] is analyses[0]
    assert all(shared is context for _, shared in calls)
    assert analyses == [flows.Analysis("延迟下降，但仅凭这些资料不能判断原因。", task)]
    assert analyses[0].evidence is task
    assert result is reports[0]
    assert result == (
        "面向：项目组\n"
        "结论：延迟下降，但仅凭这些资料不能判断原因。\n"
        "证据：平均延迟从 120 ms 降至 90 ms。（来源：压测记录）"
    )
    assert context == flows.ResearchContext("项目组", "压测记录", ["analyze", "report"])


def test_change_flow_handoffs_and_shared_context(monkeypatch: pytest.MonkeyPatch) -> None:
    task = "将请求超时配置调整为 10 秒。"
    context = flows.ChangeContext("补充超时测试")
    calls: list[tuple[object, object]] = []
    plans: list[flows.ChangePlan] = []
    opinions: list[flows.ReviewOpinion] = []
    original_plan = flows.fake_plan
    original_review = flows.fake_review

    async def observe_plan(value: str, shared: flows.ChangeContext) -> flows.ChangePlan:
        calls.append((value, shared))
        result = await original_plan(value, shared)
        plans.append(result)
        return result

    async def observe_review(
        value: flows.ChangePlan, shared: flows.ChangeContext
    ) -> flows.ReviewOpinion:
        calls.append((value, shared))
        assert shared.events == ["plan"]
        result = await original_review(value, shared)
        opinions.append(result)
        return result

    monkeypatch.setattr(flows, "fake_plan", observe_plan)
    monkeypatch.setattr(flows, "fake_review", observe_review)

    result = asyncio.run(flows.manual_b(task, context))

    assert len(calls) == 2
    assert calls[0][0] is task
    assert calls[1][0] is plans[0]
    assert all(shared is context for _, shared in calls)
    assert plans == [flows.ChangePlan(task, ("修改超时配置", "补充超时测试"))]
    assert plans[0].goal is task
    assert result is opinions[0]
    assert result == flows.ReviewOpinion(True, "方案包含要求的测试步骤。")
    assert context == flows.ChangeContext("补充超时测试", ["plan", "review"])


def test_rejection_is_a_business_result_without_revision() -> None:
    context = flows.ChangeContext("补充回滚方案")

    result = asyncio.run(flows.manual_b("将请求超时配置调整为 10 秒。", context))

    assert result == flows.ReviewOpinion(False, "方案缺少要求的测试步骤。")
    assert context.events == ["plan", "review"]
