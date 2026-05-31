"""A tiny ``name -> implementation`` registry.

Shared by the pluggable families (methods, affinity builders, clustering
strategies). Adding a variant is "write a class, register it"; nothing that
iterates the registry needs to change.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str):
        self._kind = kind
        self._items: dict[str, T] = {}

    def register(self, name: str) -> Callable[[T], T]:
        """Decorator that registers the decorated object under ``name``."""
        def decorator(obj: T) -> T:
            if name in self._items:
                raise ValueError(f"{self._kind} {name!r} is already registered")
            self._items[name] = obj
            return obj
        return decorator

    def get(self, name: str) -> T:
        try:
            return self._items[name]
        except KeyError:
            raise KeyError(
                f"unknown {self._kind} {name!r}; available: {self.names()}"
            ) from None

    def names(self) -> list[str]:
        return sorted(self._items)

    def __contains__(self, name: str) -> bool:
        return name in self._items
