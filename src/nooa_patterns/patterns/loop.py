"""Bounded feedback using complete sequential rounds and an explicit predicate."""

from collections.abc import Callable
from typing import Any, ClassVar

from ..members import Members
from .sequential import Sequential


class Loop:
    """Run at least one complete round, checking until only after its last member.

    until 应是纯函数式同步判断，不应调用 LLM 或做 I/O。
    Model evaluation belongs in an asynchronous member. The predicate must
    return bool; truthy objects are not coerced. The first round receives the
    entry task, later rounds receive the previous round's final result, and
    all calls share the original context reference. None is an ordinary value.
    Applications must make the final output compatible with the next input,
    for example with an explicit feedback-conversion member at the end.

    max_iterations is required and must be a positive int, excluding bool:
    non-ints/bools raise TypeError, zero/negative integers raise ValueError.
    A True predicate on the last allowed round is still normal termination.
    Otherwise the limit returns the last business result without raising an
    exhaustion error. No result wrapper, context writes, history or
    on_exhausted callback is added. Errors and cancellation propagate without
    retry or rollback. Direct run calls also reject empty Members.

    Applications can observe exhaustion with a fresh closure per execution::

        async def run_once(members, task, context, max_iterations):
            rounds, last_ok = 0, False

            def until(result, shared):
                nonlocal rounds, last_ok
                rounds += 1
                last_ok = check(result, shared)  # Application's pure check.
                return last_ok

            team = Team(members, Loop(until, max_iterations=max_iterations))
            result = await team.execute(task, context)
            exhausted = rounds == max_iterations and not last_ok
            return result, exhausted

    Counting observes rather than changes the business decision. The closure
    belongs to the application and must not be shared across independent
    concurrent calls. Loop does not reset closures or members. Its own round
    progress is local; only until and max_iterations are fixed configuration.
    Exceptions/cancellation skip the computation after normal return above.
    """

    requires_named_members: ClassVar[bool] = False

    def __init__(
        self, until: Callable[[Any, Any], bool], *, max_iterations: int
    ) -> None:
        if isinstance(max_iterations, bool) or not isinstance(max_iterations, int):
            raise TypeError("max_iterations must be an int, not bool")
        if max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        self.until = until
        self.max_iterations = max_iterations

    async def run(self, members: Members, task: Any, context: Any) -> Any:
        if not members:
            raise ValueError("Loop requires at least one member")
        current = task
        sequence = Sequential()
        for _ in range(self.max_iterations):
            current = await sequence.run(members, current, context)
            stop = self.until(current, context)
            if not isinstance(stop, bool):
                raise TypeError("until must return bool")
            if stop:
                return current
        # 保持契约一致：Pattern 不破例向应用 context 注入状态。
        # 固定字段在重复 / 嵌套运行中没有通用的清除与覆盖方案。
        # 耗尽状态属于应用语义，因此不写标记，也不加入记录回调。
        return current
