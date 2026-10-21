"""Deterministic allocation for control tests; never a production planner hook."""

from typing import Any

from nooa_patterns import Team


class ScriptedTeam(Team):
    def __init__(self, *args, assignments=None, **kwargs):
        super().__init__(*args, llm=None, **kwargs)
        self.assignments = assignments
        self.allocations = []

    async def allocate(self, task: Any, context: Any):
        self.allocations.append((task, context))
        if self.assignments is not None:
            return self.assignments
        return {name: {"task": task, "context": context} for name in self.members}
