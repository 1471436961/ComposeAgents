"""Public protocols and lightweight recursive collaboration primitives."""

from .adapters import as_member
from .patterns import Sequential
from .protocols import Pattern, TeamMember
from .team import Team

__all__ = ["Pattern", "Sequential", "Team", "TeamMember", "as_member"]
