"""LangGraph graphs, keyed by run type. Populated from milestone M2 onward."""

from collections.abc import Awaitable, Callable
from typing import Any

from joby_agents.db.models import RunQueue

# run type -> coroutine that executes the run. Empty in M0: the worker fails
# runs of unregistered types instead of leaving them queued.
GraphRunner = Callable[[RunQueue], Awaitable[Any]]
REGISTRY: dict[str, GraphRunner] = {}
