"""Plain Python collaboration patterns."""

from .parallel import Parallel
from .router import Router
from .sequential import Sequential

__all__ = ["Parallel", "Router", "Sequential"]
