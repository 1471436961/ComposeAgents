"""Public protocols and lightweight recursive collaboration primitives."""

from .adapters import as_member
from .patterns import Parallel, Sequential
from .protocols import Pattern, TeamMember
from .team import Team

__all__ = ["Parallel", "Pattern", "Sequential", "Team", "TeamMember", "as_member"]
