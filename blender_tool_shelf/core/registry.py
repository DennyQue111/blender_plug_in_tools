"""Runtime registry for shelf plugins."""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType


@dataclass(frozen=True)
class PluginInfo:
    module_name: str
    display_name: str


class PluginRegistry:
    """Small registry that keeps plugin discovery independent from the UI."""

    def __init__(self) -> None:
        self._modules: list[ModuleType] = []

    def add(self, module: ModuleType) -> None:
        if module not in self._modules:
            self._modules.append(module)

    def clear(self) -> None:
        self._modules.clear()

    @property
    def plugins(self) -> tuple[ModuleType, ...]:
        return tuple(self._modules)
