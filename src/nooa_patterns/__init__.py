"""Public protocols, callable adaptation and sequential collaboration."""

from .adapters import as_member
from .patterns import Sequential
from .protocols import Pattern, TeamMember

__all__ = ["Pattern", "Sequential", "TeamMember", "as_member"]
