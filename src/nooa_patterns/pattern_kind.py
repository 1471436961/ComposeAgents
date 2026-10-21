"""The four closed collaboration algorithms implemented by Team."""

from enum import Enum


class PatternKind(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ROUTER = "router"
    LOOP = "loop"
