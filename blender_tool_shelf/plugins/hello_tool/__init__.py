"""Reference plugin showing the expected plugin contract."""

from __future__ import annotations

import bpy


class BTS_OT_hello_tool(bpy.types.Operator):
    bl_idname = "bts.hello_tool"
    bl_label = "Hello Tool"
    bl_description = "Run the reference tool hosted by Blender Tool Shelf"

    def execute(self, context: bpy.types.Context) -> set[str]:
        self.report({"INFO"}, "Blender Tool Shelf is ready for new tools")
        return {"FINISHED"}


CLASSES = (BTS_OT_hello_tool,)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
