"""Fresh-state comparisons for the three-report Parallel example."""

import asyncio
from collections import Counter

import pytest

from examples import parallel_review as flows
from nooa_patterns import Sequential, Team, as_member


class _Reviewers:
    def __init__(self) -> None:
        self._feasibility = flows.fake_feasibility
        self._risk = flows.fake_risk
        self._cost = flows.fake_cost
        self.calls: list[str] = []
        self.inputs: list[flows.Proposal] = []
        self.contexts: list[flows.ReviewContext] = []
        self.results: dict[str, flows.AnalysisReport] = {}

    def record(self, name: str, task: flows.Proposal, context: flows.ReviewContext) -> None:
        self.calls.append(name)
        self.inputs.append(task)
        self.contexts.append(context)

    async def feasibility(
        self, task: flows.Proposal, context: flows.ReviewContext
    ) -> flows.FeasibilityReport:
        self.record("feasibility", task, context)
        result = await self._feasibility(task, context)
        self.results["feasibility"] = result
        return result

    async def risk(self, task: flows.Proposal, context: flows.ReviewContext) -> flows.RiskReport:
        self.record("risk", task, context)
        result = await self._risk(task, context)
        self.results["risk"] = result
        return result

    async def cost(self, task: flows.Proposal, context: flows.ReviewContext) -> flows.CostReport:
        self.record("cost", task, context)
        result = await self._cost(task, context)
        self.results["cost"] = result
        return result


def test_manual_and_composed_analyses_use_fresh_state_and_keep_report_identities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = flows.Proposal("升级认证组件。", "降低故障风险")
    outputs: list[list[flows.AnalysisReport]] = []
    contexts: list[flows.ReviewContext] = []
    reviewers: list[_Reviewers] = []
    names = ["feasibility", "risk", "cost"]

    for run in (flows.manual_analyze, flows.composed_analyze):
        context, members = flows.ReviewContext(), _Reviewers()
        assert context.events == [] and members.calls == []
        with monkeypatch.context() as patch:
            patch.setattr(flows, "fake_feasibility", members.feasibility)
            patch.setattr(flows, "fake_risk", members.risk)
            patch.setattr(flows, "fake_cost", members.cost)
            result = asyncio.run(run(task, context))

        assert len(result) == 3
        assert all(result[i] is members.results[name] for i, name in enumerate(names))
        assert len(members.inputs) == len(members.contexts) == 3
        assert all(value is task for value in members.inputs)
        assert all(shared is context for shared in members.contexts)
        assert Counter(members.calls) == Counter(context.events) == Counter(names)
        outputs.append(result)
        contexts.append(context)
        reviewers.append(members)

    assert reviewers[0] is not reviewers[1]
    assert contexts[0] is not contexts[1]
    assert contexts[0].events is not contexts[1].events
    assert outputs[0] == outputs[1]
    assert flows.aggregate(outputs[0]) == flows.aggregate(outputs[1])
    assert Counter(contexts[0].events) == Counter(contexts[1].events)


def test_parallel_child_team_passes_heterogeneous_reports_to_plain_aggregation() -> None:
    task = flows.Proposal("升级认证组件。", "降低故障风险")
    context = flows.ReviewContext()
    child = flows.build_analysis_team()
    received: list[list[flows.AnalysisReport]] = []
    bundles: list[flows.AnalysisBundle] = []

    async def aggregate_bridge(
        reports: list[flows.AnalysisReport], shared: flows.ReviewContext
    ) -> flows.AnalysisBundle:
        assert shared is context
        received.append(reports)
        bundle = flows.aggregate(reports)
        assert bundle.feasibility is reports[0]
        assert bundle.risk is reports[1]
        assert bundle.cost is reports[2]
        bundles.append(bundle)
        return bundle

    outer = Team([child, as_member(aggregate_bridge)], Sequential())
    result = asyncio.run(outer.execute(task, context))

    assert outer.members[0] is child
    assert len(received) == len(bundles) == 1
    assert result is bundles[0]
    assert result.risk.level == "high"
    assert Counter(context.events) == Counter(["feasibility", "risk", "cost"])


@pytest.mark.parametrize("run", [flows.manual_analyze, flows.composed_analyze], ids=["manual", "team"])
def test_both_coordinators_cancel_other_analyses_on_failure(
    monkeypatch: pytest.MonkeyPatch, run
) -> None:
    failure = ValueError("scripted feasibility failure")
    context = flows.ReviewContext()
    task = flows.Proposal("升级认证组件。", "降低故障风险")

    async def scenario() -> None:
        risk_started, cost_started = asyncio.Event(), asyncio.Event()
        cancelled: set[str] = set()
        jobs: list[asyncio.Task] = []

        async def fail(value: flows.Proposal, shared: flows.ReviewContext) -> flows.FeasibilityReport:
            assert value is task and shared is context
            shared.events.append("feasibility")
            await asyncio.gather(risk_started.wait(), cost_started.wait())
            raise failure

        async def risk(value: flows.Proposal, shared: flows.ReviewContext) -> flows.RiskReport:
            assert value is task and shared is context
            jobs.append(asyncio.current_task())
            shared.events.append("risk")
            risk_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.add("risk")
                raise

        async def cost(value: flows.Proposal, shared: flows.ReviewContext) -> flows.CostReport:
            assert value is task and shared is context
            jobs.append(asyncio.current_task())
            shared.events.append("cost")
            cost_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.add("cost")
                raise

        monkeypatch.setattr(flows, "fake_feasibility", fail)
        monkeypatch.setattr(flows, "fake_risk", risk)
        monkeypatch.setattr(flows, "fake_cost", cost)
        async with asyncio.timeout(5):
            with pytest.raises(ValueError) as caught:
                await run(task, context)
        assert caught.value is failure
        assert cancelled == {"risk", "cost"}
        assert len(jobs) == 2 and all(job.done() and job.cancelled() for job in jobs)

    asyncio.run(scenario())
    assert Counter(context.events) == Counter(["feasibility", "risk", "cost"])


def test_business_aggregation_rejects_missing_or_misordered_reports() -> None:
    feasibility = flows.FeasibilityReport(True, "fixture")
    risk = flows.RiskReport("low", "fixture")
    cost = flows.CostReport(2)
    with pytest.raises(ValueError):
        flows.aggregate([feasibility, risk])
    with pytest.raises(TypeError):
        flows.aggregate([risk, feasibility, cost])
