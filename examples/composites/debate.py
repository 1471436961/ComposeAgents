"""Copyable fake Debate: a LOOP Team contains parallel proposals and a judge.

Run with python -m examples.composites.debate, or by file path.
Later proposals read previous opponents' claims and the judge's feedback.
The fake judge accepts once both speakers respond; this is no quality metric.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from nooa_patterns import PatternKind, Team, as_member


@dataclass(frozen=True)
class State:
    topic: str
    arguments: tuple[Argument, ...] = ()
    accepted: bool = False
    feedback: tuple[str, ...] = ()


@dataclass(frozen=True)
class Argument:
    speaker: str
    claim: str
    replies: tuple[str, ...]
    judge_feedback: tuple[str, ...]
    source: State = field(repr=False)


@dataclass
class Context:
    events: list[str] = field(default_factory=list)
    judgments: list[State] = field(default_factory=list)


@dataclass(frozen=True)
class Outcome:
    """Application observation, constructed only after a normal Team return."""

    result: State
    rounds: int
    accepted: bool
    exhausted: bool


class FakeAdvocate:
    def __init__(self, name: str, claim: str, *, responds: bool = True) -> None:
        self.name, self.claim, self.responds = name, claim, responds
        self.calls: list[tuple[State, Context]] = []
        self.results: list[Argument] = []

    async def execute(self, task: State, context: Context) -> Argument:
        self.calls.append((task, context))
        await asyncio.sleep(0)  # Yield like an asynchronous proposal call.
        context.events.append(f"propose:{self.name}")
        # This fake responds only when the judge requested another exchange.
        replies = (tuple(a.claim for a in task.arguments if a.speaker != self.name)
                   if self.responds and task.feedback else ())
        argument = Argument(self.name, self.claim, replies, task.feedback, task)
        self.results.append(argument)
        return argument


async def adjudicate(arguments: list[Argument], context: Context) -> State:
    if len(arguments) != 2 or arguments[0].speaker == arguments[1].speaker:
        raise ValueError("This example requires two different speakers")
    source = arguments[0].source
    if any(argument.source is not source for argument in arguments):
        raise ValueError("Proposals must address the same debate state")
    context.events.append("adjudicate")
    accepted = all(bool(argument.replies) for argument in arguments)
    feedback = () if accepted else ("请回应上一轮对方观点，再提交裁决。",)
    # This business member produces the next round's compatible State directly.
    result = State(source.topic, tuple(arguments), accepted, feedback)
    context.judgments.append(result)
    return result


def make_advocates(*, responds: bool = True) -> list[FakeAdvocate]:
    return [FakeAdvocate("performance", "缓存热点读取，降低延迟。"),
            FakeAdvocate("reliability", "先明确失效策略，避免陈旧数据。", responds=responds)]


class _Proposals(Team):
    async def allocate(self, task, context):
        state = context["feedback"].get("result", context["materials"]["initial"])
        app = context["materials"]["application"]
        return {name: {"task": f"Present {name}'s argument and respond to prior feedback",
            "context": {"state": state, "application": app}} for name in self.members}


class _Debate(Team):
    async def allocate(self, task, context):
        return {
            "proposals": {"task": "Obtain independent arguments", "context": {"initial": task, "application": context}},
            "judge": {"task": "Adjudicate the actual named arguments", "context": context},
        }


def build_team(
    advocates: list[FakeAdvocate], until: Callable[[State, Context], bool], *, max_iterations: int
) -> Team:
    def bridge(advocate):
        async def propose(task, context):
            return await advocate.execute(context["materials"]["state"], context["materials"]["application"])
        return as_member(propose)
    proposals = _Proposals({a.name: bridge(a) for a in advocates}, PatternKind.PARALLEL, llm=None)
    async def judge(task, context):
        named = context["upstream"]["proposals"]
        # Explicit application conversion, not implicit flattening by Team.
        return await adjudicate([named[a.name] for a in advocates], context["materials"])
    return _Debate({"proposals": proposals, "judge": as_member(judge)}, PatternKind.LOOP,
        llm=None, until=until, max_iterations=max_iterations)


async def composed(
    task: State, context: Context, advocates: list[FakeAdvocate], *, max_iterations: int
) -> Outcome:
    rounds, accepted = 0, False

    def until(result: State, shared: Context) -> bool:
        nonlocal rounds, accepted
        rounds += 1
        accepted = result.accepted
        return accepted

    result = await build_team(advocates, until, max_iterations=max_iterations).execute(task, context)
    return Outcome(result, rounds, accepted, rounds == max_iterations and not accepted)


async def manual(
    task: State, context: Context, advocates: list[FakeAdvocate], *, max_iterations: int
) -> Outcome:
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int):
        raise TypeError("max_iterations must be an int, not bool")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    current, rounds, accepted = task, 0, False
    for _ in range(max_iterations):
        jobs = [asyncio.create_task(member.execute(current, context)) for member in advocates]
        collected = asyncio.gather(*jobs)
        try:
            arguments = await asyncio.shield(collected)
        except BaseException:
            for job in jobs:
                if not job.done():
                    job.cancel()
            await asyncio.gather(collected, *jobs, return_exceptions=True)
            raise
        current = await adjudicate(arguments, context)
        rounds += 1
        accepted = current.accepted
        if accepted:
            break
    return Outcome(current, rounds, accepted, rounds == max_iterations and not accepted)


async def main() -> None:
    for label, limit, responds, expected_rounds, expected_ok in (
        ("early", 3, True, 2, True),
        ("last-allowed", 2, True, 2, True),
        ("exhausted", 3, False, 3, False),
    ):
        runs = []
        for execute in (manual, composed):
            context, advocates = Context(), make_advocates(responds=responds)
            result = await execute(State("是否引入读取缓存？"), context, advocates, max_iterations=limit)
            assert result.rounds == expected_rounds and result.accepted is expected_ok
            assert result.exhausted is (expected_rounds == limit and not expected_ok)
            assert len(context.judgments) == expected_rounds
            assert Counter(context.events) == Counter({"propose:performance": expected_rounds,
                                                      "propose:reliability": expected_rounds,
                                                      "adjudicate": expected_rounds})
            runs.append((result, context.judgments))
        assert runs[0] == runs[1]
        print(f"{label}: rounds={result.rounds}, accepted={result.accepted}, exhausted={result.exhausted}")
    print("Debate handwritten/composed comparisons passed (fake only).")


if __name__ == "__main__":
    asyncio.run(main())
