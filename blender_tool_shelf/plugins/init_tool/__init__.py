"""Basic scene-initialization tools."""

from __future__ import annotations

import bpy


class BTS_OT_init_position(bpy.types.Operator):
    """Center an unparented mesh at the world origin and freeze its location."""

    bl_idname = "bts.init_position"
    bl_label = "Init Position"
    bl_description = "Set the mesh origin to its vertex center, move it to world origin, and apply location"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and obj.parent is None

    def execute(self, context: bpy.types.Context) -> set[str]:
        obj = context.active_object
        assert obj is not None
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
        obj.location = (0.0, 0.0, 0.0)
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
        self.report({"INFO"}, f"Initialized {obj.name}: origin and location are at world origin")
        return {"FINISHED"}


CLASSES = (BTS_OT_init_position,)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
