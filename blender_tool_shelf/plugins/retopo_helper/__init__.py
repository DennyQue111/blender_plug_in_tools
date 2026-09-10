"""First MVP of the in-house retopology helper.

This version creates a new mesh and places vertices on the active high-poly
mesh using viewport ray-casting.  It deliberately keeps the scope small so
that the interaction and surface-snapping foundations are easy to inspect.
"""

from __future__ import annotations

import bpy
from bpy_extras import view3d_utils


class BTS_OT_start_retopo_helper(bpy.types.Operator):
    """Create a retopo mesh and place vertices on the selected high-poly mesh."""

    bl_idname = "bts.start_retopo_helper"
    bl_label = "Retopo Helper"
    bl_description = "Click on the active mesh to place snapped retopology vertices"

    source_object: bpy.types.Object | None = None
    retopo_object: bpy.types.Object | None = None
    points: list[tuple[float, float, float]]

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        source = context.active_object
        if source is None or source.type != "MESH":
            self.report({"WARNING"}, "Select a mesh object to use as the high-poly surface")
            return {"CANCELLED"}

        self.source_object = source
        self.points = []
        mesh = bpy.data.meshes.new("BTS_Retopo")
        self.retopo_object = bpy.data.objects.new("BTS_Retopo", mesh)
        context.collection.objects.link(self.retopo_object)

        for obj in context.selected_objects:
            obj.select_set(False)
        self.retopo_object.select_set(True)
        context.view_layer.objects.active = self.retopo_object

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        if event.type in {"ESC", "RIGHTMOUSE", "RET"} and event.value == "PRESS":
            return self._finish(context)

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            hit = self._raycast(context, event)
            if hit is not None:
                self.points.append(tuple(hit))
                self._update_mesh()
                if context.area:
                    context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        return {"RUNNING_MODAL", "PASS_THROUGH"}

    def _raycast(
        self, context: bpy.types.Context, event: bpy.types.Event
    ) -> tuple[float, float, float] | None:
        region = context.region
        space = context.space_data
        if region is None or space is None or not hasattr(space, "region_3d"):
            return None

        coord = (event.mouse_region_x, event.mouse_region_y)
        origin = view3d_utils.region_2d_to_origin_3d(region, space.region_3d, coord)
        direction = view3d_utils.region_2d_to_vector_3d(region, space.region_3d, coord)
        depsgraph = context.evaluated_depsgraph_get()
        hit, location, _normal, _face_index, hit_object, _matrix = context.scene.ray_cast(
            depsgraph, origin, direction
        )
        if hit and hit_object == self.source_object:
            return location
        return None

    def _update_mesh(self) -> None:
        mesh = self.retopo_object.data
        mesh.clear_geometry()
        mesh.from_pydata(self.points, [], [])
        mesh.update()

    def _finish(self, context: bpy.types.Context) -> set[str]:
        self.report({"INFO"}, f"Placed {len(self.points)} retopo vertices")
        return {"FINISHED"}


CLASSES = (BTS_OT_start_retopo_helper,)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)