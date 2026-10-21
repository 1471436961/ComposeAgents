"""Named recursive Teams, semantic allocation and four fixed collaborations."""

from .adapters import as_member
from .pattern_kind import PatternKind
from .protocols import TeamMember
from .team import AllocationError, Team

__all__ = [
    "AllocationError", "PatternKind", "Team", "TeamMember", "as_member"
]
