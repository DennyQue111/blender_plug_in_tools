"""Blender-side controls for the external local VGGT scene service."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ImportHelper


def _service_url(scene: bpy.types.Scene, path: str) -> str:
    return scene.bts_vggt_service_url.rstrip("/") + path


def _request_json(url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


class BTS_OT_pick_concept_image(bpy.types.Operator, ImportHelper):
    bl_idname = "bts.pick_concept_image"
    bl_label = "Choose Concept Image"
    bl_description = "Choose the concept or reference image sent to the local VGGT service"

    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.webp;*.tif;*.tiff", options={"HIDDEN"}
    )

    def execute(self, context: bpy.types.Context) -> set[str]:
        context.scene.bts_concept_image_path = self.filepath
        context.scene.bts_vggt_job_status = "Image selected"
        return {"FINISHED"}


class BTS_OT_submit_vggt_job(bpy.types.Operator):
    bl_idname = "bts.submit_vggt_job"
    bl_label = "Generate VGGT Scene Data"
    bl_description = "Submit the selected image to the local VGGT scene service"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(context.scene.bts_concept_image_path)

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        image_path = Path(scene.bts_concept_image_path).expanduser()
        if not image_path.is_file():
            self.report({"ERROR"}, "Choose an existing concept image first")
            return {"CANCELLED"}

        try:
            result = _request_json(
                _service_url(scene, "/jobs"),
                {
                    "image_path": str(image_path.resolve()),
                    "bundle_adjustment": scene.bts_vggt_bundle_adjustment,
                },
            )
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            scene.bts_vggt_job_status = f"Service unavailable: {exc}"
            self.report({"ERROR"}, "Cannot reach local VGGT service on port 8765")
            return {"CANCELLED"}

        job_id = result.get("job_id")
        status_url = result.get("status_url")
        if not isinstance(job_id, str) or not isinstance(status_url, str):
            self.report({"ERROR"}, "VGGT service returned an invalid job response")
            return {"CANCELLED"}

        scene.bts_vggt_job_id = job_id
        scene.bts_vggt_status_path = status_url
        scene.bts_vggt_job_status = "Queued"
        self.report({"INFO"}, f"VGGT job {job_id[:8]} queued")
        return {"FINISHED"}


class BTS_OT_check_vggt_job(bpy.types.Operator):
    bl_idname = "bts.check_vggt_job"
    bl_label = "Check VGGT Job"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(context.scene.bts_vggt_status_path)

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        try:
            result = _request_json(_service_url(scene, scene.bts_vggt_status_path))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            scene.bts_vggt_job_status = f"Status request failed: {exc}"
            self.report({"ERROR"}, "Cannot read VGGT job status")
            return {"CANCELLED"}

        status = result.get("status", "unknown")
        error = result.get("error")
        scene.bts_vggt_job_status = str(status if not error else f"{status}: {error}")
        self.report({"INFO"}, f"VGGT job status: {status}")
        return {"FINISHED"}


CLASSES = (
    BTS_OT_pick_concept_image,
    BTS_OT_submit_vggt_job,
    BTS_OT_check_vggt_job,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bts_concept_image_path = StringProperty(subtype="FILE_PATH")
    bpy.types.Scene.bts_vggt_service_url = StringProperty(default="http://127.0.0.1:8765")
    bpy.types.Scene.bts_vggt_bundle_adjustment = BoolProperty(default=False)
    bpy.types.Scene.bts_vggt_job_id = StringProperty(options={"HIDDEN"})
    bpy.types.Scene.bts_vggt_status_path = StringProperty(options={"HIDDEN"})
    bpy.types.Scene.bts_vggt_job_status = StringProperty(default="Service not contacted")


def unregister() -> None:
    for name in (
        "bts_vggt_job_status",
        "bts_vggt_status_path",
        "bts_vggt_job_id",
        "bts_vggt_bundle_adjustment",
        "bts_vggt_service_url",
        "bts_concept_image_path",
    ):
        delattr(bpy.types.Scene, name)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)