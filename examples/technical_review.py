"""Four collaborations in one fake technical-review application.

Run: python -m examples.technical_review. All allocate overrides are scripted
demo fixtures. Production Team uses its native NOOA generation instead. Manual
and composed paths share these business functions; no real model is called.
"""

import asyncio
from dataclasses import dataclass, field

from nooa_patterns import PatternKind as K, Team, as_member


@dataclass(frozen=True)
class Proposal:
    text: str
    goal: str


@dataclass(frozen=True)
class FeasibilityReport:
    feasible: bool


@dataclass(frozen=True)
class RiskReport:
    level: str


@dataclass(frozen=True)
class CostReport:
    engineer_days: int


@dataclass(frozen=True)
class AnalysisBundle:
    feasibility: FeasibilityReport
    risk: RiskReport
    cost: CostReport


@dataclass(frozen=True)
class ReviewRequest:
    proposal: Proposal
    bundle: AnalysisBundle


@dataclass(frozen=True)
class ReviewOpinion:
    request: ReviewRequest
    reviewer: str
    accepted: bool


@dataclass
class ReviewContext:
    events: list[str] = field(default_factory=list)
    reviews: list[ReviewOpinion] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewRun:
    result: Proposal
    rounds: int
    accepted: bool
    exhausted: bool


async def feasibility(proposal: Proposal, context: ReviewContext) -> FeasibilityReport:
    """Return a scripted feasibility finding for this proposal."""
    await asyncio.sleep(0)
    context.events.append("feasibility")
    return FeasibilityReport(True)


async def risk(proposal: Proposal, context: ReviewContext) -> RiskReport:
    """Classify authentication as high risk, database as medium, other as low."""
    await asyncio.sleep(0)
    context.events.append("risk")
    return RiskReport("high" if "认证" in proposal.text else "medium" if "数据库" in proposal.text else "low")


async def cost(proposal: Proposal, context: ReviewContext) -> CostReport:
    await asyncio.sleep(0)
    context.events.append("cost")
    return CostReport(2 + len(proposal.text) // 20)


def aggregate(proposal: Proposal, reports: dict) -> ReviewRequest:
    expected = {"feasibility": FeasibilityReport, "risk": RiskReport, "cost": CostReport}
    if reports.keys() != expected.keys():
        raise ValueError("Expected named feasibility, risk and cost reports")
    if any(not isinstance(reports[name], cls) for name, cls in expected.items()):
        raise TypeError("A named analysis has the wrong business type")
    return ReviewRequest(proposal, AnalysisBundle(**reports))


def select_by_risk(request: ReviewRequest, context) -> str:
    """Select security / architecture / quick for high / medium / low risk."""
    return {"high": "security", "medium": "architecture", "low": "quick"}[request.bundle.risk.level]


class Reviewer:
    def __init__(self, name):
        self.name = name
        self.calls = []

    async def review(self, request: ReviewRequest, context: ReviewContext) -> ReviewOpinion:
        """Accept a rollback-enabled proposal unless external approval is blocked."""
        self.calls.append(request)
        context.events.append(f"review:{self.name}")
        opinion = ReviewOpinion(request, self.name,
            "回滚开关" in request.proposal.text and "外部审批未完成" not in request.proposal.text)
        context.reviews.append(opinion)
        return opinion


def make_reviewers():
    return {name: Reviewer(name) for name in ("security", "architecture", "quick")}


async def feedback(opinion: ReviewOpinion, context: ReviewContext) -> Proposal:
    context.events.append("feedback")
    proposal = opinion.request.proposal
    if not opinion.accepted and "回滚开关" not in proposal.text:
        return Proposal(proposal.text + " 补充回滚开关。", proposal.goal)
    return proposal


class _Analysis(Team):
    async def allocate(self, task, context):
        proposal = context["feedback"].get("result", context["materials"]["initial"])
        app = context["materials"]["application"]
        return {name: {"task": f"Analyze {name} only", "context": {
            "proposal": proposal, "application": app}} for name in self.members}


class _Review(Team):
    async def allocate(self, task, context):
        request = context["upstream"]["aggregate"]
        return {name: {"task": f"Perform {name} review", "context": {
            "request": request, "application": context["materials"]}} for name in self.members}


class _ReviewLoop(Team):
    async def allocate(self, task, context):
        return {
            "analysis": {"task": "Obtain three independent analyses", "context": {"initial": task, "application": context}},
            "aggregate": {"task": "Combine actual named reports", "context": {"initial": task, "application": context}},
            "review": {"task": "Choose one reviewer for the actual request", "context": context},
            "feedback": {"task": "Provide a proposal for the next round", "context": context},
        }


def build_team(reviewers, until, *, max_iterations, selector=select_by_risk):
    def analyst(fn):
        async def execute(task, context):
            material = context["materials"]
            return await fn(material["proposal"], material["application"])
        return as_member(execute)
    analyses = _Analysis({"feasibility": analyst(feasibility), "risk": analyst(risk), "cost": analyst(cost)},
        K.PARALLEL, llm=None)
    async def combine(task, context):
        proposal = context["feedback"].get("result", context["materials"]["initial"])
        return aggregate(proposal, context["upstream"]["analysis"])
    def reviewer(member):
        async def execute(task, context):
            return await member.review(context["materials"]["request"], context["materials"]["application"])
        return as_member(execute)
    def route(task, context):
        return selector(context["upstream"]["aggregate"], context["materials"])
    review = _Review({name: reviewer(member) for name, member in reviewers.items()}, K.ROUTER,
        llm=None, selector=route)
    async def convert(task, context):
        return await feedback(context["upstream"]["review"], context["materials"])
    return _ReviewLoop({"analysis": analyses, "aggregate": as_member(combine), "review": review,
        "feedback": as_member(convert)}, K.LOOP, llm=None, until=until, max_iterations=max_iterations)


async def composed_review(task, context, reviewers, *, max_iterations, selector=select_by_risk):
    rounds, last_ok = 0, False
    def until(result, original_context):
        nonlocal rounds, last_ok
        rounds += 1
        last_ok = original_context.reviews[-1].accepted
        return last_ok
    team = build_team(reviewers, until, max_iterations=max_iterations, selector=selector)
    result = await team.execute(task, context)
    return ReviewRun(result, rounds, last_ok, rounds == max_iterations and not last_ok)


async def manual_review(task, context, reviewers, *, max_iterations, selector=select_by_risk):
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int):
        raise TypeError("max_iterations must be an integer, not bool")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    current, accepted = task, False
    for index in range(max_iterations):
        jobs = {name: asyncio.create_task(fn(current, context))
            for name, fn in (("feasibility", feasibility), ("risk", risk), ("cost", cost))}
        collected = asyncio.gather(*jobs.values())
        try:
            reports = dict(zip(jobs, await asyncio.shield(collected), strict=True))
        except BaseException:
            for job in jobs.values():
                if not job.done():
                    job.cancel()
            await asyncio.gather(collected, *jobs.values(), return_exceptions=True)
            raise
        request = aggregate(current, reports)
        selected = selector(request, context)
        if not isinstance(selected, str):
            raise TypeError("selector must return a string")
        if selected not in reviewers:
            raise LookupError(f"selector returned {selected!r}, available: {list(reviewers)!r}")
        opinion = await reviewers[selected].review(request, context)
        current = await feedback(opinion, context)
        accepted = opinion.accepted
        if accepted:
            break
    rounds = index + 1
    return ReviewRun(current, rounds, accepted, rounds == max_iterations and not accepted)


async def main():
    for text, limit, rounds, accepted in [
        ("升级认证组件并保留回滚开关。", 3, 1, True),
        ("修改数据库索引。", 2, 2, True),
        ("调整日志格式。", 1, 1, False),
        ("外部审批未完成。", 3, 3, False),
    ]:
        runs = []
        for execute in (manual_review, composed_review):
            app = ReviewContext()
            result = await execute(Proposal(text, "控制变更风险"), app, make_reviewers(), max_iterations=limit)
            assert result.rounds == rounds and result.accepted is accepted
            runs.append((result, sorted(app.events)))
        assert runs[0] == runs[1]
        print(f"rounds={rounds}, accepted={accepted}, exhausted={result.exhausted}")
    print("Technical-review handwritten/composed comparisons passed (fake only).")


if __name__ == "__main__":
    asyncio.run(main())
