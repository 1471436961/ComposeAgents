"""Copyable fake EvaluatorOptimizer: Loop around an explicit Sequential round.

Run with python -m examples.composites.evaluator_optimizer, or by file path.
Generation, evaluation and feedback are application code, not new Patterns.
The deterministic writer adds one requested item per round; no LLM is called.
"""

import asyncio
from dataclasses import dataclass, field

from nooa_patterns import Loop, Sequential, Team, as_member


@dataclass(frozen=True)
class Request:
    goal: str
    required: tuple[str, ...]
    text: str = ""
    feedback: tuple[str, ...] = ()


@dataclass(frozen=True)
class Draft:
    request: Request
    text: str


@dataclass(frozen=True)
class Evaluation:
    draft: Draft
    missing: tuple[str, ...]


@dataclass
class Context:
    events: list[str] = field(default_factory=list)
    evaluations: list[Evaluation] = field(default_factory=list)


@dataclass(frozen=True)
class Outcome:
    """Application observation; the Team itself returns an ordinary Request."""

    result: Request
    rounds: int
    accepted: bool
    exhausted: bool


class FakeGenerator:
    def __init__(self) -> None:
        self.calls: list[tuple[Request, Context]] = []
        self.results: list[Draft] = []

    async def execute(self, task: Request, context: Context) -> Draft:
        self.calls.append((task, context))
        context.events.append("generate")
        pending = task.feedback or tuple(item for item in task.required if item not in task.text)
        addition = pending[0] if pending else ""
        text = "；".join(part for part in (task.text, addition) if part)
        draft = Draft(task, text)
        self.results.append(draft)
        return draft


async def evaluate(draft: Draft, context: Context) -> Evaluation:
    context.events.append("evaluate")
    result = Evaluation(draft, tuple(item for item in draft.request.required if item not in draft.text))
    context.evaluations.append(result)
    return result


async def feedback(evaluation: Evaluation, context: Context) -> Request:
    context.events.append("feedback")
    original = evaluation.draft.request
    # Explicitly close the type cycle: Request -> Draft -> Evaluation -> Request.
    return Request(original.goal, original.required, evaluation.draft.text, evaluation.missing)


def build_round(generator: FakeGenerator) -> Team:
    return Team([generator, as_member(evaluate), as_member(feedback)], Sequential())


async def composed(
    task: Request, context: Context, generator: FakeGenerator, *, max_iterations: int
) -> Outcome:
    rounds, accepted = 0, False

    def until(result: Request, shared: Context) -> bool:
        nonlocal rounds, accepted
        rounds += 1
        accepted = not result.feedback
        return accepted

    team = Team([build_round(generator)], Loop(until, max_iterations=max_iterations))
    result = await team.execute(task, context)
    return Outcome(result, rounds, accepted, rounds == max_iterations and not accepted)


async def manual(
    task: Request, context: Context, generator: FakeGenerator, *, max_iterations: int
) -> Outcome:
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int):
        raise TypeError("max_iterations must be an int, not bool")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    current, rounds, accepted = task, 0, False
    for _ in range(max_iterations):
        draft = await generator.execute(current, context)
        evaluation = await evaluate(draft, context)
        current = await feedback(evaluation, context)
        rounds += 1
        accepted = not evaluation.missing
        if accepted:
            break
    return Outcome(current, rounds, accepted, rounds == max_iterations and not accepted)


async def main() -> None:
    for label, required, limit, expected_rounds, expected_ok in (
        ("early", ("目标",), 3, 1, True),
        ("last-allowed", ("目标", "测试", "回滚"), 3, 3, True),
        ("exhausted", ("目标", "测试", "回滚"), 2, 2, False),
    ):
        runs = []
        for execute in (manual, composed):
            context, generator = Context(), FakeGenerator()
            result = await execute(Request("发布说明", required), context, generator, max_iterations=limit)
            assert result.rounds == expected_rounds and result.accepted is expected_ok
            assert result.exhausted is (expected_rounds == limit and not expected_ok)
            assert context.events == ["generate", "evaluate", "feedback"] * expected_rounds
            runs.append((result, context))
        assert runs[0] == runs[1]
        print(f"{label}: rounds={result.rounds}, accepted={result.accepted}, exhausted={result.exhausted}")
    print("EvaluatorOptimizer handwritten/composed comparisons passed (fake only).")


if __name__ == "__main__":
    asyncio.run(main())
