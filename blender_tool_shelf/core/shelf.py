"""Blender UI for the shared tool shelf."""

from __future__ import annotations

import bpy


class VIEW3D_PT_tool_shelf(bpy.types.Panel):
    bl_label = "Tool Shelf"
    bl_idname = "VIEW3D_PT_blender_tool_shelf"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool Shelf"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text="Blender Tool Shelf", icon="TOOL_SETTINGS")
        layout.separator()
        box = layout.box()
        box.label(text="Installed tools", icon="PLUGIN")
        box.operator("bts.hello_tool", icon="SOLO_ON")


SHELF_CLASSES = (VIEW3D_PT_tool_shelf,)
