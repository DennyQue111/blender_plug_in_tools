"""Blender Tool Shelf.

This package is intentionally installable as a normal Blender add-on.  New
tools should live in ``plugins/<plugin_name>`` and expose a ``register`` and
``unregister`` function.
"""

from __future__ import annotations

import importlib

import bpy

from .core.registry import PluginRegistry
from .core.shelf import SHELF_CLASSES
from .plugins import discover_plugins

bl_info = {
    "name": "Blender Tool Shelf",
    "author": "Denny",
    "version": (0, 1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Tool Shelf",
    "description": "A maintainable shelf for developing and hosting Blender tools",
    "category": "3D View",
}

_registry = PluginRegistry()
_loaded_plugins: list[object] = []


def register() -> None:
    for cls in SHELF_CLASSES:
        bpy.utils.register_class(cls)

    for module in discover_plugins():
        module = importlib.import_module(module) if isinstance(module, str) else module
        if hasattr(module, "register"):
            module.register()
        _registry.add(module)
        _loaded_plugins.append(module)


def unregister() -> None:
    for module in reversed(_loaded_plugins):
        if hasattr(module, "unregister"):
            module.unregister()
    _loaded_plugins.clear()
    _registry.clear()

    for cls in reversed(SHELF_CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
