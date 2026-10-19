"""Full review routing compares fresh runs and checks business object handoffs."""

import asyncio
from collections import Counter

import pytest

from examples import router_review as flows
from nooa_patterns import Parallel, Router, Sequential


class _AnalysisProbe:
    def __init__(self) -> None:
        self.original_feasibility = flows.analysis.fake_feasibility
        self.original_risk = flows.fake_risk
        self.original_cost = flows.analysis.fake_cost
        self.inputs: list[flows.analysis.Proposal] = []
        self.contexts: list[flows.ReviewContext] = []
        self.results: dict[str, flows.analysis.AnalysisReport] = {}

    async def feasibility(
        self, task: flows.analysis.Proposal, context: flows.ReviewContext
    ) -> flows.analysis.FeasibilityReport:
        self.inputs.append(task)
        self.contexts.append(context)
        result = await self.original_feasibility(task, context)
        self.results["feasibility"] = result
        return result

    async def risk(
        self, task: flows.analysis.Proposal, context: flows.ReviewContext
    ) -> flows.analysis.RiskReport:
        self.inputs.append(task)
        self.contexts.append(context)
        result = await self.original_risk(task, context)
        self.results["risk"] = result
        return result

    async def cost(
        self, task: flows.analysis.Proposal, context: flows.ReviewContext
    ) -> flows.analysis.CostReport:
        self.inputs.append(task)
        self.contexts.append(context)
        result = await self.original_cost(task, context)
        self.results["cost"] = result
        return result


@pytest.mark.parametrize(
    ("text", "level", "expected"),
    [("升级认证组件。", "high", "security"),
     ("修改数据库索引。", "medium", "architecture"),
     ("调整日志格式。", "low", "quick")],
    ids=["high", "medium", "low"],
)
def test_manual_and_composed_reviews_have_equal_values_and_isolated_state(
    monkeypatch: pytest.MonkeyPatch, text: str, level: str, expected: str
) -> None:
    task = flows.analysis.Proposal(text, "保持服务稳定")
    runs = []
    for composed in (False, True):
        context = flows.ReviewContext(proposal=task)
        probe, reviewers = _AnalysisProbe(), flows.make_reviewers()
        decisions: list[tuple[flows.ReviewRequest, flows.ReviewContext]] = []

        def selector(request: flows.ReviewRequest, shared: flows.ReviewContext) -> str:
            decisions.append((request, shared))
            return flows.select_by_risk(request, shared)

        with monkeypatch.context() as patch:
            patch.setattr(flows.analysis, "fake_feasibility", probe.feasibility)
            patch.setattr(flows, "fake_risk", probe.risk)
            patch.setattr(flows.analysis, "fake_cost", probe.cost)
            if composed:
                team = flows.build_review_team(reviewers, selector)
                assert isinstance(team.pattern, Sequential)
                assert isinstance(team.members[0].pattern, Parallel)
                assert isinstance(team.members[2].pattern, Router)
                result = asyncio.run(team.execute(task, context))
            else:
                result = asyncio.run(flows.manual_review(task, context, reviewers, selector))

        assert len(probe.inputs) == len(probe.contexts) == 3
        assert all(value is task for value in probe.inputs)
        assert all(shared is context for shared in probe.contexts)
        assert len(decisions) == len(reviewers[expected].calls) == 1
        request, shared = reviewers[expected].calls[0]
        assert decisions[0][0] is request and decisions[0][1] is shared is context
        assert request.proposal is task and context.proposal is task
        assert request.bundle.feasibility is probe.results["feasibility"]
        assert request.bundle.risk is probe.results["risk"]
        assert request.bundle.cost is probe.results["cost"]
        assert request.bundle.risk.level == level
        assert all(member.calls == [] for name, member in reviewers.items() if name != expected)
        assert result is reviewers[expected].results[0]
        assert context.events[-1] == f"review:{expected}"
        assert Counter(context.events[:-1]) == Counter(["feasibility", "risk", "cost"])
        runs.append((result, context, probe, reviewers, request))

    left, right = runs
    assert left[0] == right[0]
    assert Counter(left[1].events) == Counter(right[1].events)
    assert left[1] is not right[1] and left[1].events is not right[1].events
    assert left[2] is not right[2]
    assert all(left[3][name] is not right[3][name] for name in left[3])
    assert left[4] is not right[4] and left[4].bundle is not right[4].bundle


def test_selector_replacement_preserves_the_business_reviewers_and_analysis_contract() -> None:
    reviewers = flows.make_reviewers()
    by_risk = flows.build_review_team(reviewers, flows.select_by_risk)
    always_quick = flows.build_review_team(reviewers, lambda request, context: "quick")
    task = flows.analysis.Proposal("升级认证组件。", "控制风险")

    conservative = asyncio.run(by_risk.execute(task, flows.ReviewContext(proposal=task)))
    fast = asyncio.run(always_quick.execute(task, flows.ReviewContext(proposal=task)))
    assert conservative.reviewer == "security" and fast.reviewer == "quick"
    assert all(by_risk.members[2].members[name] is always_quick.members[2].members[name]
               is reviewers[name] for name in reviewers)
    assert len(reviewers["security"].calls) == len(reviewers["quick"].calls) == 1
    assert reviewers["architecture"].calls == []


def test_wrong_router_structure_fails_before_any_analysis_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = []

    async def unexpected(task, context):
        started.append(task)
        raise AssertionError("Analysis must not start during construction")

    monkeypatch.setattr(flows.analysis, "fake_feasibility", unexpected)
    monkeypatch.setattr(flows, "fake_risk", unexpected)
    monkeypatch.setattr(flows.analysis, "fake_cost", unexpected)
    with pytest.raises(ValueError, match="Router requires named members"):
        flows.build_review_team(list(flows.make_reviewers().values()))
    assert started == []


def test_unknown_route_does_not_execute_a_reviewer_or_undo_finished_analysis() -> None:
    task = flows.analysis.Proposal("升级认证组件。", "控制风险")
    context, reviewers = flows.ReviewContext(proposal=task), flows.make_reviewers()
    team = flows.build_review_team(reviewers, lambda request, shared: "unknown")
    with pytest.raises(LookupError, match=r"available: \['security', 'architecture', 'quick'\]"):
        asyncio.run(team.execute(task, context))
    assert Counter(context.events) == Counter(["feasibility", "risk", "cost"])
    assert all(member.calls == [] for member in reviewers.values())


def test_analysis_failure_cancels_peers_and_never_reaches_the_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = flows.analysis.Proposal("升级认证组件。", "控制风险")
    context, reviewers = flows.ReviewContext(proposal=task), flows.make_reviewers()
    failure = ValueError("analysis failed")
    decisions = []

    async def scenario() -> None:
        risk_started, cost_started = asyncio.Event(), asyncio.Event()
        cancelled = set()

        async def fail(value, shared):
            shared.events.append("feasibility")
            await asyncio.gather(risk_started.wait(), cost_started.wait())
            raise failure

        async def wait_risk(value, shared):
            shared.events.append("risk")
            risk_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.add("risk")

        async def wait_cost(value, shared):
            shared.events.append("cost")
            cost_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.add("cost")

        def selector(request, shared):
            decisions.append(request)
            return "security"

        monkeypatch.setattr(flows.analysis, "fake_feasibility", fail)
        monkeypatch.setattr(flows, "fake_risk", wait_risk)
        monkeypatch.setattr(flows.analysis, "fake_cost", wait_cost)
        team = flows.build_review_team(reviewers, selector)
        async with asyncio.timeout(5):
            with pytest.raises(ValueError) as caught:
                await team.execute(task, context)
        assert caught.value is failure and cancelled == {"risk", "cost"}

    asyncio.run(scenario())
    assert decisions == [] and all(member.calls == [] for member in reviewers.values())
    assert Counter(context.events) == Counter(["feasibility", "risk", "cost"])
