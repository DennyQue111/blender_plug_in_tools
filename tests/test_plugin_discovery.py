from blender_tool_shelf.plugins import ENABLED_PLUGINS, discover_plugins


def test_plugin_discovery_is_explicit_and_deterministic():
    assert discover_plugins() == (
        "blender_tool_shelf.plugins.init_tool",
        "blender_tool_shelf.plugins.retopo_helper",
        "blender_tool_shelf.plugins.concept_scene",
    )
    assert "blender_tool_shelf.plugins.init_tool" in discover_plugins()
