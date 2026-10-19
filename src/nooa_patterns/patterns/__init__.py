"""Plain Python collaboration patterns."""

from .loop import Loop
from .parallel import Parallel
from .router import Router
from .sequential import Sequential

__all__ = ["Loop", "Parallel", "Router", "Sequential"]
