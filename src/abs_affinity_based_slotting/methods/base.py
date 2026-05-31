"""Contract for slotting methods (the Strategy that produces an assignment)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..registry import Registry
from ..slotting import Assignment, SlottingInstance


@runtime_checkable
class SlottingMethod(Protocol):
    """A strategy that places the instance's SKUs into locations.

    Implementations work internally in index space and return an id-based
    :class:`Assignment` covering every SKU of the instance.
    """

    name: str

    def solve(self, instance: SlottingInstance) -> Assignment: ...


#: name -> SlottingMethod subclass. Iterated by the experiment harness.
method_registry: Registry[type[SlottingMethod]] = Registry("method")
