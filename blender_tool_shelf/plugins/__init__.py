"""Plugin discovery for the tool shelf.

Keep discovery explicit and deterministic.  A plugin is enabled by adding
its package name to ``ENABLED_PLUGINS``; this prevents accidental imports of
unfinished folders while developing.
"""

from __future__ import annotations

ENABLED_PLUGINS = (
    "blender_tool_shelf.plugins.hello_tool",
)


def discover_plugins() -> tuple[str, ...]:
    return ENABLED_PLUGINS
