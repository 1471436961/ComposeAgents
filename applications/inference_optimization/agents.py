"""NOOA specialists. Prompts describe research duties, never a project's answer."""

from nooa import Agent, strategy
from nooa.config import CodeActConfig
from nooa.strategies import CodeActStrategy

from .models import (
    ChangeReport, ExperimentPlan, Findings, ImplementationPacket, IterationResult,
    PlanningPacket, Review,
)
from .workspace import EditTools, ReadTools, Workspace


def _codeact():
    return CodeActStrategy(config=CodeActConfig(
        max_iterations=12, max_retries=1, cell_timeout=60, max_tokens=4096,
    ))


def _predecessor(context: dict, name: str, kind):
    value = context["upstream"][name]
    if not isinstance(value, kind):
        raise TypeError(f"{name} must return {kind.__name__}")
    return value


class Researcher(Agent):
    """Investigate assigned inference questions, citing evidence and uncertainty.

    Treat requested optimization techniques as hypotheses. Inspect actual source,
    graph and environment before recommending kernels, precision or a runtime.
    Never assert a measurement was run without a recorded command. Use tools
    selectively; do not load repository history or unrelated project solutions.
    This role investigates and does not edit implementation source.
    """

    def __init__(self, workspace: Workspace, role: str, *, llm):
        super().__init__(llm=llm)
        self.tools = ReadTools(workspace, role)

    @strategy(_codeact())
    async def execute(self, task: str, context: dict) -> Findings:
        """Investigate the local instruction using materials and tools.

        Return observations with file/command citations, separate hypotheses,
        and unresolved questions. Read any previous-round findings/review in the
        allocated materials. Report unavailable resources honestly; do not
        install dependencies or mutate system configuration to acquire them.
        """
        ...


class ModelAnalyst(Researcher):
    """Model/graph analyst: verify actual operations, tensor shapes, model and
    dataset assumptions, numerical requirements and candidate fusion boundaries.
    User descriptions may be wrong; cite implementation evidence. Inherit the
    research discipline of separating evidence, hypotheses and unknowns.
    """


class RuntimeAnalyst(Researcher):
    """Runtime/performance analyst: inspect available hardware, toolchains,
    memory, deployment constraints and reproducible profiling methodology.
    Do not assume a runtime, precision or accelerator is supported. Separate
    measured bottlenecks from guesses; prefer a small reproducible probe.
    """


class Planner(Agent):
    """Design one bounded inference experiment from independent investigations.
    Preserve semantic correctness and meaningful end-to-end acceptance criteria.
    Do not implement changes or assume custom kernels necessarily improve speed.
    """

    @strategy(_codeact())
    async def plan(self, instruction: str, findings: dict[str, Findings],
                   previous: IterationResult | None, materials: object) -> ExperimentPlan:
        """Reconcile evidence and conflicting hypotheses, then choose one experiment.

        Use previous review feedback to change the next experiment. State explicit
        correctness/performance checks and risks. A missing tool/data/permission
        is a constraint to report, not permission to install, spend or change scope.
        """
        ...

    async def execute(self, task: str, context: dict) -> PlanningPacket:
        """Consume the named investigate result and carry it with the real plan.

        Assigned task must be a string. Only materials are allocation-selected;
        investigations come from upstream['investigate'], and the previous full
        iteration from feedback['result']. Do not fabricate future results.
        """
        findings = _predecessor(context, "investigate", dict)
        if set(findings) != {"model", "runtime"} or not all(
            isinstance(value, Findings) for value in findings.values()
        ):
            raise TypeError("investigate must return named model/runtime Findings")
        previous = context["feedback"].get("result")
        plan = await self.plan(task, findings, previous, context["materials"])
        return PlanningPacket(findings=findings, plan=plan)


class Implementer(Agent):
    """Inference implementation engineer: make the planned, bounded change.
    Work only in the supplied workspace. Use source inspection, small probes and
    recorded checks; preserve baseline artifacts and report negative results.
    Do not touch another project, install software, change system settings, spend
    money or terminate unrelated processes. Ask for missing resources via the
    report. Never invent successful compilation, timings or accuracy numbers.
    """

    def __init__(self, workspace: Workspace, *, llm):
        super().__init__(llm=llm)
        self.tools = EditTools(workspace, "implementer")
        self._workspace = workspace

    @strategy(_codeact())
    async def implement(self, instruction: str, planning: PlanningPacket,
                        materials: object) -> ChangeReport:
        """Execute the bounded plan using tools, returning artifacts and command IDs.

        Paths are workspace-relative. Cite actual command IDs, preserve raw data,
        and distinguish implemented, tested, and unavailable work. Avoid broad
        rewrites. No autonomous dependency installs, external downloads, commits,
        pushes or background processes. Large output remains in evidence files.
        """
        ...

    async def execute(self, task: str, context: dict) -> ImplementationPacket:
        """Implement upstream['plan']; carry its real findings/plan to validation."""
        planning = _predecessor(context, "plan", PlanningPacket)
        start = len(self._workspace.commands)
        changes = await self.implement(task, planning, context["materials"])
        self._workspace.verify_evidence(changes.command_ids, role="implementer", after=start)
        for artifact in changes.artifacts:
            if not self._workspace.path(artifact).is_file():
                raise ValueError(f"reported artifact does not exist: {artifact!r}")
        return ImplementationPacket(planning=planning, changes=changes)


class Validator(Agent):
    """Independent correctness/performance validator, not the implementation author.
    Read the requirements, evidence, plan and changed artifacts. Execute your own
    checks using tools; do not edit implementation source or accept another role's
    success claim as proof. Check numerical agreement and benchmark comparability.
    Acceptance covers the requested deliverables, not just a successful command.
    Missing resources or permission must be reported as blocked, not passed.
    """

    def __init__(self, workspace: Workspace, *, llm):
        super().__init__(llm=llm)
        self.tools = ReadTools(workspace, "validator")
        self._workspace = workspace

    @strategy(_codeact())
    async def verify(self, instruction: str, implementation: ImplementationPacket,
                     materials: object) -> Review:
        """Run independent checks; accepted/revise/blocked with evidence and feedback.

        Cite your own command IDs. Metrics require real raw evidence; when not
        measured leave metrics empty. Accepted requires independently executed
        checks and fulfillment of the user's requirements. Revise feedback should
        identify a concrete next experiment. Do not mask exceptions as exhaustion.
        """
        ...

    async def execute(self, task: str, context: dict) -> IterationResult:
        """Validate upstream['implement']; return the complete iteration packet.

        Carry real upstream records, rather than ask a model to reproduce them.
        This packet becomes Loop feedback. No global history is concatenated.
        """
        implementation = _predecessor(context, "implement", ImplementationPacket)
        start = len(self._workspace.commands)
        review = await self.verify(task, implementation, context["materials"])
        self._workspace.verify_evidence(
            review.command_ids, role="validator", after=start,
            success_required=review.verdict == "accepted",
        )
        previous = context["feedback"].get("result")
        iteration = 1 if previous is None else previous.iteration + 1
        return IterationResult(iteration=iteration, implementation=implementation, review=review)
