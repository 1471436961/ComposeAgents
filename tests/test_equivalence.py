"""Compare business values across fresh runs; check identity within each run."""

import asyncio

import pytest

from examples import composed_flows as composed
from examples import manual_flows as flows


class _ResearchSteps:
    """Fresh stateful observers around the unchanged baseline business logic."""

    def __init__(self) -> None:
        self._analyze = flows.fake_analyze
        self._report = flows.fake_write_report
        self.calls = 0
        self.task: str | None = None
        self.analysis: flows.Analysis | None = None
        self.report_input: flows.Analysis | None = None
        self.result: str | None = None
        self.contexts: list[flows.ResearchContext] = []

    async def analyze(self, task: str, context: flows.ResearchContext) -> flows.Analysis:
        self.calls += 1
        self.task = task
        self.contexts.append(context)
        self.analysis = await self._analyze(task, context)
        return self.analysis

    async def report(self, task: flows.Analysis, context: flows.ResearchContext) -> str:
        self.calls += 1
        self.report_input = task
        self.contexts.append(context)
        self.result = await self._report(task, context)
        return self.result


class _ChangeSteps:
    def __init__(self) -> None:
        self._plan = flows.fake_plan
        self._review = flows.fake_review
        self.calls = 0
        self.task: str | None = None
        self.plan_result: flows.ChangePlan | None = None
        self.review_input: flows.ChangePlan | None = None
        self.result: flows.ReviewOpinion | None = None
        self.contexts: list[flows.ChangeContext] = []

    async def plan(self, task: str, context: flows.ChangeContext) -> flows.ChangePlan:
        self.calls += 1
        self.task = task
        self.contexts.append(context)
        self.plan_result = await self._plan(task, context)
        return self.plan_result

    async def review(
        self, task: flows.ChangePlan, context: flows.ChangeContext
    ) -> flows.ReviewOpinion:
        self.calls += 1
        self.review_input = task
        self.contexts.append(context)
        self.result = await self._review(task, context)
        return self.result


def test_research_manual_and_composed_are_equivalent_with_isolated_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = "平均延迟从 120 ms 降至 90 ms。"
    results: list[str] = []
    contexts: list[flows.ResearchContext] = []
    observers: list[_ResearchSteps] = []

    for run in (flows.manual_a, composed.composed_a):
        context = flows.ResearchContext("项目组", "压测记录")
        steps = _ResearchSteps()
        assert steps.calls == 0
        assert context.events == []
        with monkeypatch.context() as patch:
            patch.setattr(flows, "fake_analyze", steps.analyze)
            patch.setattr(flows, "fake_write_report", steps.report)
            result = asyncio.run(run(task, context))

        assert steps.calls == 2
        assert steps.task is task
        assert steps.analysis is not None
        assert steps.analysis.evidence is task
        assert steps.report_input is steps.analysis
        assert result is steps.result
        assert len(steps.contexts) == 2
        assert all(shared is context for shared in steps.contexts)
        assert context.events == ["analyze", "report"]
        results.append(result)
        contexts.append(context)
        observers.append(steps)

    assert observers[0] is not observers[1]
    assert contexts[0] is not contexts[1]
    assert contexts[0].events is not contexts[1].events
    assert observers[0].analysis == observers[1].analysis
    assert results[0] == results[1]
    assert contexts[0] == contexts[1]


@pytest.mark.parametrize(
    ("required_step", "expected"),
    [
        ("补充超时测试", flows.ReviewOpinion(True, "方案包含要求的测试步骤。")),
        ("补充回滚方案", flows.ReviewOpinion(False, "方案缺少要求的测试步骤。")),
    ],
    ids=["accepted", "rejected-without-revision"],
)
def test_change_manual_and_composed_are_equivalent_with_isolated_state(
    monkeypatch: pytest.MonkeyPatch,
    required_step: str,
    expected: flows.ReviewOpinion,
) -> None:
    task = "将请求超时配置调整为 10 秒。"
    results: list[flows.ReviewOpinion] = []
    contexts: list[flows.ChangeContext] = []
    observers: list[_ChangeSteps] = []

    for run in (flows.manual_b, composed.composed_b):
        context = flows.ChangeContext(required_step)
        steps = _ChangeSteps()
        assert steps.calls == 0
        assert context.events == []
        with monkeypatch.context() as patch:
            patch.setattr(flows, "fake_plan", steps.plan)
            patch.setattr(flows, "fake_review", steps.review)
            result = asyncio.run(run(task, context))

        assert steps.calls == 2
        assert steps.task is task
        assert steps.plan_result is not None
        assert steps.plan_result.goal is task
        assert steps.review_input is steps.plan_result
        assert result is steps.result
        assert result == expected
        assert len(steps.contexts) == 2
        assert all(shared is context for shared in steps.contexts)
        assert context.events == ["plan", "review"]
        results.append(result)
        contexts.append(context)
        observers.append(steps)

    assert observers[0] is not observers[1]
    assert contexts[0] is not contexts[1]
    assert contexts[0].events is not contexts[1].events
    assert observers[0].plan_result == observers[1].plan_result
    assert results[0] == results[1]
    assert contexts[0] == contexts[1]
