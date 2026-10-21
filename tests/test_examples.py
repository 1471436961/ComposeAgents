"""Application values, branch reuse and feedback against handwritten baselines."""

import asyncio

import pytest

from examples import manual_flows as baseline, composed_flows as composed, technical_review as review


@pytest.mark.parametrize("flow", ["research", "accepted", "rejected"])
def test_baseline_business_values_survive_local_input_adaptation(flow):
    if flow == "research":
        functions, factory = (baseline.manual_a, composed.composed_a), lambda: baseline.ResearchContext("项目组", "压测")
    else:
        functions, factory = (baseline.manual_b, composed.composed_b), lambda: baseline.ChangeContext(
            "补充超时测试" if flow == "accepted" else "补充回滚方案")
    outcomes = []
    for fn in functions:
        app = factory()
        result = asyncio.run(fn("fixture input", app))
        outcomes.append((result, app))
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][1] is not outcomes[1][1]
    assert outcomes[0][1].events is not outcomes[1][1].events


@pytest.mark.parametrize("text,limit,rounds,accepted,reviewer", [
    ("认证变更。 回滚开关", 3, 1, True, "security"),
    ("数据库索引。", 2, 2, True, "architecture"),
    ("日志变更。", 1, 1, False, "quick"),
    ("外部审批未完成。", 3, 3, False, "quick"),
])
def test_review_manual_composed_equivalence_and_exhaustion(text, limit, rounds, accepted, reviewer):
    runs = []
    for fn in (review.manual_review, review.composed_review):
        app, workers = review.ReviewContext(), review.make_reviewers()
        result = asyncio.run(fn(review.Proposal(text, "目标"), app, workers, max_iterations=limit))
        assert result.rounds == rounds and result.accepted is accepted
        assert result.exhausted is (rounds == limit and not accepted)
        assert len(app.reviews) == rounds
        assert all(r.reviewer == reviewer for r in app.reviews)
        assert len(workers[reviewer].calls) == rounds
        assert all(not w.calls for name, w in workers.items() if name != reviewer)
        assert "loop_exhausted" not in vars(app)
        runs.append((result, app))
    assert runs[0][0] == runs[1][0] and sorted(runs[0][1].events) == sorted(runs[1][1].events)
    assert runs[0][1] is not runs[1][1]


def test_selector_change_reuses_business_members_in_new_teams():
    workers = review.make_reviewers()
    context_a, context_b = review.ReviewContext(), review.ReviewContext()
    task = review.Proposal("认证变更。 回滚开关", "目标")
    async def scenario():
        left = await review.composed_review(task, context_a, workers, max_iterations=1)
        right = await review.composed_review(task, context_b, workers, max_iterations=1,
            selector=lambda request, app: "quick")
        assert left.accepted and right.accepted
    asyncio.run(scenario())
    assert context_a.reviews[0].reviewer == "security" and context_b.reviews[0].reviewer == "quick"
    assert workers["security"].calls[0].proposal is task and workers["quick"].calls[0].proposal is task


@pytest.mark.parametrize("fn", [review.manual_review, review.composed_review])
def test_unknown_route_preserves_analysis_effects_without_review(fn):
    app, workers = review.ReviewContext(), review.make_reviewers()
    with pytest.raises(LookupError, match="available"):
        asyncio.run(fn(review.Proposal("变更", "目标"), app, workers, max_iterations=1,
            selector=lambda request, app: "missing"))
    assert sorted(app.events) == ["cost", "feasibility", "risk"]
    assert not app.reviews and all(not w.calls for w in workers.values())


@pytest.mark.parametrize("reports,exc", [({}, ValueError),
    ({"feasibility": None, "risk": review.RiskReport("low"), "cost": review.CostReport(2)}, TypeError)])
def test_named_aggregation_rejects_missing_or_wrong_business_results(reports, exc):
    with pytest.raises(exc):
        review.aggregate(review.Proposal("change", "goal"), reports)


def test_named_aggregation_does_not_depend_on_dictionary_insertion_order():
    reports = {"cost": review.CostReport(2), "risk": review.RiskReport("low"),
        "feasibility": review.FeasibilityReport(True)}
    result = review.aggregate(review.Proposal("change", "goal"), reports)
    assert result.bundle.cost is reports["cost"] and result.bundle.risk is reports["risk"]
