"""Application composition; native Team allocation and algorithms stay intact."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from nooa_patterns import PatternKind, Team

from .agents import Implementer, ModelAnalyst, Planner, RuntimeAnalyst, Validator
from .models import IterationResult, RunResult
from .workspace import Workspace


class InvestigationTeam(Team):
    """Parallel model/graph and runtime/performance investigation.

    Receive an instruction string and parent local context. Allocate different
    questions/materials to model and runtime analysts, returning a named dict of
    Findings. Allocation must use string tasks. Previous review is available for
    updating investigations; do not pass all root context to every analyst.
    """

    async def execute(self, task: str, context: dict) -> dict:
        """Reallocate each investigation using current parent feedback.

        selected_materials holds the parent-assigned evidence; previous_iteration
        is the actual last result, unavailable in round one. It is provided for
        targeted selection, never a replacement for fresh source/command evidence.
        """
        return await super().execute(task, {
            "selected_materials": context["materials"],
            "previous_iteration": context["feedback"].get("result"),
        })


def _finished(result: IterationResult, context: dict) -> bool:
    """Stop after an accepted or resource/permission-blocked review; otherwise revise."""
    return result.review.verdict in {"accepted", "blocked"}


class InferenceOptimizationTeam(Team):
    """A bounded inference optimization R&D team for a caller-supplied project.

    Every round: investigate (parallel model/runtime Findings), plan a bounded
    experiment, implement, independently verify. Use string task assignments for
    all members. The user requirement and environment constraints are application
    inputs, not assumptions about a particular model, GPU, runtime or solution.
    Select only relevant materials for each member. Direct upstream packets carry
    actual evidence/plans/changes; previous iteration feedback updates decisions.
    Preserve end-to-end delivery requirements, including in validation tasks.
    """

    def __init__(self, members: dict, *, llm: Any, max_rounds: int, workspace: Workspace):
        super().__init__(members, PatternKind.LOOP, llm=llm,
                         until=_finished, max_iterations=max_rounds)
        self._workspace = workspace

    async def execute(self, task: str, context: dict | None = None) -> RunResult:
        """Receive project requirements plus environment/constraints; return a run record.

        Use a fresh team/workspace for an independent run. Errors and cancellation
        propagate with evidence retained; they are never labeled exhausted. Caller
        owns the outer deadline, model clients, permission and spending limits.
        """
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a nonempty requirements string")
        start = time.perf_counter()
        result = await super().execute(task, {} if context is None else context)
        if not isinstance(result, IterationResult):
            raise TypeError("validator must return IterationResult")
        status = result.review.verdict
        if status == "revise":
            status = "exhausted"
        outcome = RunResult(
            status=status, rounds=result.iteration, elapsed_seconds=time.perf_counter() - start,
            last=result, evidence_directory=str(self._workspace.evidence_directory),
        )
        self._workspace.evidence_path("result.json").write_text(
            outcome.model_dump_json(indent=2), encoding="utf-8",
        )
        return outcome


def build_team(workspace: Workspace, *, llm: Any, max_rounds: int,
               role_llms: Mapping[str, Any] | None = None) -> InferenceOptimizationTeam:
    """Build immutable Teams with native allocation, no planner override or LLM call.

    llm supplies all Team allocations and is the default leaf client/model.
    Optional per-role clients allow cost/quality choices; callers own them all.
    No role/task/optimization is specialized to the first evaluation project.
    """
    overrides = {} if role_llms is None else dict(role_llms)
    names = {"model", "runtime", "planner", "implementer", "validator"}
    if overrides.keys() - names:
        raise ValueError(f"unknown role models: {sorted(overrides.keys() - names)}")
    models = {name: overrides.get(name, llm) for name in names}
    investigations = InvestigationTeam({
        "model": ModelAnalyst(workspace, "model", llm=models["model"]),
        "runtime": RuntimeAnalyst(workspace, "runtime", llm=models["runtime"]),
    }, PatternKind.PARALLEL, llm=llm)
    return InferenceOptimizationTeam({
        "investigate": investigations,
        "plan": Planner(llm=models["planner"]),
        "implement": Implementer(workspace, llm=models["implementer"]),
        "verify": Validator(workspace, llm=models["validator"]),
    }, llm=llm, max_rounds=max_rounds, workspace=workspace)
