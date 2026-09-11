"""Blender UI for the shared tool shelf."""

from __future__ import annotations

import bpy


class BTS_OT_refresh_shelf(bpy.types.Operator):
    """Refresh the local Extension repository and Blender add-on metadata."""

    bl_idname = "bts.refresh_shelf"
    bl_label = "Refresh Tool Shelf"
    bl_description = "Refresh the linked source directory and add-on metadata"

    def execute(self, context: bpy.types.Context) -> set[str]:
        refreshed = []

        if hasattr(bpy.ops, "extensions") and hasattr(
            bpy.ops.extensions, "repo_refresh_all"
        ):
            bpy.ops.extensions.repo_refresh_all()
            refreshed.append("extensions")

        if hasattr(bpy.ops, "preferences") and hasattr(
            bpy.ops.preferences, "addon_refresh"
        ):
            bpy.ops.preferences.addon_refresh()
            refreshed.append("add-ons")

        self.report({"INFO"}, "Tool Shelf refreshed: " + ", ".join(refreshed))
        return {"FINISHED"}


class VIEW3D_PT_tool_shelf(bpy.types.Panel):
    bl_label = "Tool Shelf"
    bl_idname = "VIEW3D_PT_blender_tool_shelf"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool Shelf"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        header = layout.row(align=True)
        header.label(text="Blender Tool Shelf", icon="TOOL_SETTINGS")
        header.operator("bts.refresh_shelf", text="", icon="FILE_REFRESH")
        layout.label(text="Choose a tool category below", icon="INFO")


class VIEW3D_PT_tool_shelf_modeling(bpy.types.Panel):
    bl_label = "Modeling"
    bl_idname = "VIEW3D_PT_blender_tool_shelf_modeling"
    bl_parent_id = "VIEW3D_PT_blender_tool_shelf"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool Shelf"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.operator("bts.hello_tool", text="Hello Tool", icon="SOLO_ON")
        layout.operator("bts.start_retopo_helper", text="Retopo Helper", icon="MESH_DATA")
        layout.separator()
        layout.operator("bts.toggle_concept_scene", text="Concept Scene", icon="IMAGE_DATA")
        if context.scene.bts_concept_scene_expanded:
            box = layout.box()
            box.prop(context.scene, "bts_concept_image_path", text="Image")
            box.prop(context.scene, "bts_vggt_service_url", text="Service")
            box.prop(context.scene, "bts_vggt_bundle_adjustment", text="Bundle Adjustment")
            box.operator("bts.submit_vggt_job", icon="PLAY")
            row = box.row(align=True)
            row.operator("bts.check_vggt_job", text="Refresh Status / Log", icon="FILE_REFRESH")
            box.label(text="Status: " + context.scene.bts_vggt_job_status)
            if context.scene.bts_vggt_log_tail:
                box.label(text="Latest VGGT log:", icon="TEXT")
                for line in context.scene.bts_vggt_log_tail.splitlines()[-4:]:
                    box.label(text=line[:88])
            if context.scene.bts_vggt_job_status == "succeeded":
                box.operator("bts.import_vggt_point_cloud", icon="MESH_DATA")


class VIEW3D_PT_tool_shelf_rigging(bpy.types.Panel):
    bl_label = "Rigging"
    bl_idname = "VIEW3D_PT_blender_tool_shelf_rigging"
    bl_parent_id = "VIEW3D_PT_blender_tool_shelf"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool Shelf"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        self.layout.label(text="No rigging tools installed yet", icon="INFO")


class VIEW3D_PT_tool_shelf_animation(bpy.types.Panel):
    bl_label = "Animation"
    bl_idname = "VIEW3D_PT_blender_tool_shelf_animation"
    bl_parent_id = "VIEW3D_PT_blender_tool_shelf"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool Shelf"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        self.layout.label(text="No animation tools installed yet", icon="INFO")


SHELF_CLASSES = (
    BTS_OT_refresh_shelf,
    VIEW3D_PT_tool_shelf,
    VIEW3D_PT_tool_shelf_modeling,
    VIEW3D_PT_tool_shelf_rigging,
    VIEW3D_PT_tool_shelf_animation,
)