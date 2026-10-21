"""Application business records, distinct from Team's weak composition protocol."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Findings(Record):
    """Separate source/measurement evidence from hypotheses and unknowns."""

    observations: list[str]
    evidence: list[str]  # Workspace-relative files or recorded command IDs.
    hypotheses: list[str]
    unknowns: list[str]


class ExperimentPlan(Record):
    """One bounded experiment, with correctness and performance acceptance rules."""

    objective: str
    changes: list[str]
    checks: list[str] = Field(min_length=1)
    risks: list[str]


class ChangeReport(Record):
    summary: str
    artifacts: list[str]
    command_ids: list[str]
    limitations: list[str]


class Review(Record):
    """A verdict about the requested deliverables, not just the latest edit.

    Accepted requires independently executed checks; blocked means a required
    resource or permission is missing. Revise requests another bounded round.
    Metrics must cite raw artifacts; never invent timings or claim unrun checks.
    """

    verdict: Literal["accepted", "revise", "blocked"]
    summary: str
    command_ids: list[str]
    metrics: dict[str, float]
    feedback: list[str]


class PlanningPacket(Record):
    findings: dict[str, Findings]
    plan: ExperimentPlan


class ImplementationPacket(Record):
    planning: PlanningPacket
    changes: ChangeReport


class IterationResult(Record):
    iteration: int = Field(ge=1)
    implementation: ImplementationPacket
    review: Review


class RunResult(Record):
    status: Literal["accepted", "blocked", "exhausted"]
    rounds: int
    elapsed_seconds: float
    last: IterationResult
    evidence_directory: str
