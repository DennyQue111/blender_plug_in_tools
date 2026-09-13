"""Blender-side controls for the external local VGGT scene service."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import bpy
from mathutils import Matrix
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

import numpy as np


def _service_url(scene: bpy.types.Scene, path: str) -> str:
    return scene.bts_vggt_service_url.rstrip("/") + path


def _request_json(url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _point_cloud_path(scene: bpy.types.Scene) -> Path:
    return Path(scene.bts_vggt_job_directory) / "input" / "scene_data" / "points.ply"


def _source_images(scene: bpy.types.Scene) -> list[Path]:
    if scene.bts_concept_input_mode == "SINGLE":
        image_path = Path(scene.bts_concept_image_path).expanduser()
        return [image_path] if image_path.is_file() else []

    image_directory = Path(scene.bts_concept_image_directory).expanduser()
    supported_suffixes = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
    if not image_directory.is_dir():
        return []
    return sorted(
        (path for path in image_directory.iterdir() if path.suffix.lower() in supported_suffixes),
        key=lambda path: path.name.casefold(),
    )


def _depth_mesh_paths(scene: bpy.types.Scene) -> tuple[Path, Path, Path, Path]:
    job_directory = Path(scene.bts_vggt_job_directory)
    data_directory = job_directory / "input" / "scene_data"
    return (
        data_directory / "depth.npy",
        data_directory / "confidence.npy",
        data_directory / "cameras.json",
        job_directory / "input" / "images",
    )


class BTS_OT_toggle_concept_scene(bpy.types.Operator):
    bl_idname = "bts.toggle_concept_scene"
    bl_label = "Concept Scene"
    bl_description = "Show or hide the Concept Scene controls"

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        scene.bts_concept_scene_expanded = not scene.bts_concept_scene_expanded
        return {"FINISHED"}


class BTS_OT_submit_vggt_job(bpy.types.Operator):
    bl_idname = "bts.submit_vggt_job"
    bl_label = "Generate VGGT Scene Data"
    bl_description = "Submit the selected image to the local VGGT scene service"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(_source_images(context.scene))

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        image_paths = _source_images(scene)
        if not image_paths:
            self.report({"ERROR"}, "Choose an existing image or a folder containing supported images")
            return {"CANCELLED"}
        if scene.bts_concept_input_mode == "FOLDER" and len(image_paths) < 2:
            self.report({"ERROR"}, "Choose a folder containing at least two scene views")
            return {"CANCELLED"}

        try:
            result = _request_json(
                _service_url(scene, "/jobs"),
                {
                    "image_paths": [str(image_path.resolve()) for image_path in image_paths],
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
        scene.bts_vggt_job_directory = ""
        scene.bts_vggt_job_status = "Queued"
        self.report({"INFO"}, f"VGGT job {job_id[:8]} queued with {len(image_paths)} image(s)")
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
        directory = result.get("directory")
        log_tail = result.get("log_tail")
        if isinstance(directory, str):
            scene.bts_vggt_job_directory = directory
        if isinstance(log_tail, str):
            scene.bts_vggt_log_tail = log_tail
        scene.bts_vggt_job_status = str(status if not error else f"{status}: {error}")
        self.report({"INFO"}, f"VGGT job status: {status}")
        return {"FINISHED"}


class BTS_OT_import_vggt_point_cloud(bpy.types.Operator):
    bl_idname = "bts.import_vggt_point_cloud"
    bl_label = "Import VGGT Point Cloud"
    bl_description = "Import the point cloud generated by the completed VGGT job"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return _point_cloud_path(context.scene).is_file()

    def execute(self, context: bpy.types.Context) -> set[str]:
        point_cloud = _point_cloud_path(context.scene)
        if not hasattr(bpy.ops.wm, "ply_import"):
            self.report({"ERROR"}, "This Blender version does not provide the PLY import operator")
            return {"CANCELLED"}

        try:
            bpy.ops.wm.ply_import(filepath=str(point_cloud))
        except RuntimeError as exc:
            self.report({"ERROR"}, f"Could not import VGGT point cloud: {exc}")
            return {"CANCELLED"}

        for obj in context.selected_objects:
            obj.name = "VGGT_PointCloud"
        self.report({"INFO"}, "VGGT point cloud imported")
        return {"FINISHED"}


class BTS_OT_create_vggt_camera(bpy.types.Operator):
    bl_idname = "bts.create_vggt_camera"
    bl_label = "Create VGGT Camera"
    bl_description = "Create a Blender camera matching VGGT's first input view"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        _depth_path, _confidence_path, cameras_path, _image_directory = _depth_mesh_paths(context.scene)
        return cameras_path.is_file()

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            import numpy as np
            camera_data = json.loads(_depth_mesh_paths(context.scene)[2].read_text(encoding="utf-8"))
            intrinsics = np.asarray(camera_data["intrinsics"][0], dtype=np.float64)
            extrinsics = np.asarray(camera_data["extrinsics_world_to_camera"][0], dtype=np.float64)
            resolution = camera_data["inference_resolution"]
        except (ImportError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            self.report({"ERROR"}, f"Could not read VGGT camera data: {exc}")
            return {"CANCELLED"}
        if intrinsics.shape != (3, 3) or extrinsics.shape[0] < 3 or extrinsics.shape[1] < 4:
            self.report({"ERROR"}, "VGGT camera matrices have an unsupported shape")
            return {"CANCELLED"}

        rotation_world_from_camera = extrinsics[:3, :3].T
        location = -rotation_world_from_camera @ extrinsics[:3, 3]
        # VGGT uses OpenCV camera axes (right, down, forward); Blender cameras use
        # (right, up, backward). Keep the scene in VGGT axes to align with the PLY/depth mesh.
        blender_camera_axes = np.diag((1.0, -1.0, -1.0))
        rotation = rotation_world_from_camera @ blender_camera_axes
        matrix = Matrix.Identity(4)
        for row in range(3):
            for column in range(3):
                matrix[row][column] = float(rotation[row, column])
            matrix[row][3] = float(location[row])

        camera_data_block = bpy.data.cameras.new("VGGT_Camera")
        image_width = int(resolution[1])
        camera_data_block.sensor_width = 36.0
        camera_data_block.lens = float(intrinsics[0, 0]) / image_width * camera_data_block.sensor_width
        camera_object = bpy.data.objects.new("VGGT_Camera", camera_data_block)
        context.collection.objects.link(camera_object)
        camera_object.matrix_world = matrix
        context.scene.camera = camera_object
        context.scene.render.resolution_x = image_width
        context.scene.render.resolution_y = int(resolution[0])
        self.report({"INFO"}, "Created and activated VGGT camera")
        return {"FINISHED"}


class BTS_OT_create_vggt_floor_proxy(bpy.types.Operator):
    bl_idname = "bts.create_vggt_floor_proxy"
    bl_label = "Create Floor Proxy"
    bl_description = "Fit an editable floor plane to reliable depth samples near the bottom of the image"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        depth_path, confidence_path, cameras_path, _image_directory = _depth_mesh_paths(context.scene)
        return depth_path.is_file() and confidence_path.is_file() and cameras_path.is_file()

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            import numpy as np
            scene = context.scene
            depth_path, confidence_path, cameras_path, _image_directory = _depth_mesh_paths(scene)
            depth = np.squeeze(np.load(depth_path))
            confidence = np.squeeze(np.load(confidence_path))
            camera_data = json.loads(cameras_path.read_text(encoding="utf-8"))
            intrinsics = np.asarray(camera_data["intrinsics"][0], dtype=np.float64)
            extrinsics = np.asarray(camera_data["extrinsics_world_to_camera"][0], dtype=np.float64)
        except (ImportError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            self.report({"ERROR"}, f"Could not read VGGT depth data: {exc}")
            return {"CANCELLED"}
        if depth.ndim != 2 or confidence.shape != depth.shape or intrinsics.shape != (3, 3):
            self.report({"ERROR"}, "VGGT depth, confidence, or camera data has an unsupported shape")
            return {"CANCELLED"}

        height, width = depth.shape
        y_start = int(height * (1.0 - scene.bts_vggt_floor_image_portion))
        inverse_intrinsics = np.linalg.inv(intrinsics)
        rotation = extrinsics[:3, :3]
        translation = extrinsics[:3, 3]
        samples: list[object] = []
        for y in range(y_start, height, 6):
            for x in range(0, width, 6):
                if not (np.isfinite(depth[y, x]) and np.isfinite(confidence[y, x])):
                    continue
                if depth[y, x] <= 0 or confidence[y, x] < scene.bts_vggt_floor_confidence:
                    continue
                camera_point = inverse_intrinsics @ np.array((x, y, 1.0)) * depth[y, x]
                samples.append(rotation.T @ (camera_point - translation))
        if len(samples) < 30:
            self.report({"ERROR"}, "Too few reliable bottom-image depth samples to fit a floor")
            return {"CANCELLED"}

        points = np.asarray(samples)
        if len(points) > 2_000:
            points = points[np.linspace(0, len(points) - 1, 2_000, dtype=np.int32)]
        tolerance = scene.bts_vggt_floor_fit_tolerance * max(float(np.median(depth)), 1e-6)
        generator = np.random.default_rng(42)
        best_mask = None
        for _ in range(160):
            a, b, c = points[generator.choice(len(points), size=3, replace=False)]
            normal = np.cross(b - a, c - a)
            normal_length = np.linalg.norm(normal)
            if normal_length < 1e-8:
                continue
            normal /= normal_length
            mask = np.abs((points - a) @ normal) <= tolerance
            if best_mask is None or mask.sum() > best_mask.sum():
                best_mask = mask
        if best_mask is None or best_mask.sum() < 20:
            self.report({"ERROR"}, "Could not identify a dominant floor plane; adjust Floor Fit Tolerance")
            return {"CANCELLED"}

        inliers = points[best_mask]
        center = inliers.mean(axis=0)
        _unused, _singular_values, vectors = np.linalg.svd(inliers - center, full_matrices=False)
        normal = vectors[-1]
        axis_u = vectors[0]
        axis_v = np.cross(normal, axis_u)
        axis_v /= np.linalg.norm(axis_v)
        projected_u = (inliers - center) @ axis_u
        projected_v = (inliers - center) @ axis_v
        padding = scene.bts_vggt_floor_padding
        u_min, u_max = projected_u.min(), projected_u.max()
        v_min, v_max = projected_v.min(), projected_v.max()
        u_padding = (u_max - u_min) * padding
        v_padding = (v_max - v_min) * padding
        corners = (
            center + axis_u * (u_min - u_padding) + axis_v * (v_min - v_padding),
            center + axis_u * (u_max + u_padding) + axis_v * (v_min - v_padding),
            center + axis_u * (u_max + u_padding) + axis_v * (v_max + v_padding),
            center + axis_u * (u_min - u_padding) + axis_v * (v_max + v_padding),
        )
        mesh = bpy.data.meshes.new("VGGT_FloorProxy")
        mesh.from_pydata([tuple(float(value) for value in point) for point in corners], [], [(0, 1, 2, 3)])
        mesh.update()
        floor = bpy.data.objects.new("VGGT_FloorProxy", mesh)
        context.collection.objects.link(floor)
        material = bpy.data.materials.new("VGGT_FloorProxy_Material")
        material.diffuse_color = (0.12, 0.55, 0.18, 1.0)
        mesh.materials.append(material)
        for object_to_deselect in context.selected_objects:
            object_to_deselect.select_set(False)
        floor.select_set(True)
        context.view_layer.objects.active = floor
        self.report({"INFO"}, f"Created floor proxy from {len(inliers):,} fitted depth samples")
        return {"FINISHED"}


class BTS_OT_create_vggt_depth_mesh(bpy.types.Operator):
    bl_idname = "bts.create_vggt_depth_mesh"
    bl_label = "Create VGGT Depth Mesh"
    bl_description = "Create a textured 2.5D mesh from the current VGGT depth prediction"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        depth_path, confidence_path, cameras_path, image_directory = _depth_mesh_paths(context.scene)
        return all((depth_path.is_file(), confidence_path.is_file(), cameras_path.is_file(), image_directory.is_dir()))

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        depth_path, confidence_path, cameras_path, image_directory = _depth_mesh_paths(scene)
        try:
            depth = np.load(depth_path)
            confidence = np.load(confidence_path)
            camera_data = json.loads(cameras_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.report({"ERROR"}, f"Could not read VGGT scene data: {exc}")
            return {"CANCELLED"}

        # VGGT currently saves depth as [frame, height, width, channel] and
        # confidence as [frame, height, width]. Remove only singleton axes;
        # repeatedly indexing [0] would incorrectly turn depth into one column.
        depth = np.squeeze(depth)
        confidence = np.squeeze(confidence)
        if depth.ndim != 2 or confidence.shape != depth.shape:
            self.report({"ERROR"}, "VGGT depth and confidence arrays have incompatible shapes")
            return {"CANCELLED"}

        try:
            intrinsics = np.asarray(camera_data["intrinsics"][0], dtype=np.float64)
            extrinsics = np.asarray(camera_data["extrinsics_world_to_camera"][0], dtype=np.float64)
            image_name = str(camera_data["images"][0])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            self.report({"ERROR"}, f"VGGT camera data is incomplete: {exc}")
            return {"CANCELLED"}
        if intrinsics.shape != (3, 3) or extrinsics.shape[0] < 3 or extrinsics.shape[1] < 4:
            self.report({"ERROR"}, "VGGT camera matrices have an unsupported shape")
            return {"CANCELLED"}

        height, width = depth.shape
        stride = scene.bts_vggt_depth_mesh_stride
        x_coordinates = list(range(0, width, stride))
        y_coordinates = list(range(0, height, stride))
        if x_coordinates[-1] != width - 1:
            x_coordinates.append(width - 1)
        if y_coordinates[-1] != height - 1:
            y_coordinates.append(height - 1)

        inverse_intrinsics = np.linalg.inv(intrinsics)
        rotation = extrinsics[:3, :3]
        translation = extrinsics[:3, 3]
        vertices: list[tuple[float, float, float]] = []
        uvs: list[tuple[float, float]] = []
        vertex_indices: dict[tuple[int, int], int] = {}
        valid = np.isfinite(depth) & np.isfinite(confidence) & (depth > 0)
        valid &= confidence >= scene.bts_vggt_depth_mesh_confidence

        for y in y_coordinates:
            for x in x_coordinates:
                if not valid[y, x]:
                    continue
                camera_point = inverse_intrinsics @ np.array((x, y, 1.0)) * depth[y, x]
                # Keep VGGT's world axes unchanged so this mesh aligns with its imported PLY.
                world_point = rotation.T @ (camera_point - translation)
                vertex_indices[(y, x)] = len(vertices)
                vertices.append(tuple(float(value) for value in world_point))
                uvs.append(((x + 0.5) / width, 1.0 - (y + 0.5) / height))

        faces: list[tuple[int, int, int]] = []
        depth_limit = scene.bts_vggt_depth_mesh_discontinuity
        for y_index in range(len(y_coordinates) - 1):
            for x_index in range(len(x_coordinates) - 1):
                y0, y1 = y_coordinates[y_index], y_coordinates[y_index + 1]
                x0, x1 = x_coordinates[x_index], x_coordinates[x_index + 1]
                keys = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))
                if not all(key in vertex_indices for key in keys):
                    continue
                cell_depth = np.array((depth[y0, x0], depth[y0, x1], depth[y1, x1], depth[y1, x0]))
                if cell_depth.max() - cell_depth.min() > depth_limit * max(cell_depth.min(), 1e-6):
                    continue
                a, b, c, d = (vertex_indices[key] for key in keys)
                faces.extend(((a, b, c), (a, c, d)))

        if not faces:
            self.report({"ERROR"}, "No mesh faces survived the depth/confidence filters")
            return {"CANCELLED"}

        mesh = bpy.data.meshes.new("VGGT_DepthMesh")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for polygon in mesh.polygons:
            for loop_index in polygon.loop_indices:
                uv_layer.data[loop_index].uv = uvs[mesh.loops[loop_index].vertex_index]

        mesh_object = bpy.data.objects.new("VGGT_DepthMesh", mesh)
        context.collection.objects.link(mesh_object)
        for object_to_deselect in context.selected_objects:
            object_to_deselect.select_set(False)
        mesh_object.select_set(True)
        context.view_layer.objects.active = mesh_object

        image_path = image_directory / image_name
        if image_path.is_file():
            image = bpy.data.images.load(str(image_path), check_existing=True)
            material = bpy.data.materials.new("VGGT_DepthMesh_Material")
            material.use_nodes = True
            nodes = material.node_tree.nodes
            links = material.node_tree.links
            texture = nodes.new("ShaderNodeTexImage")
            texture.image = image
            principled = nodes.get("Principled BSDF")
            if principled is not None:
                links.new(texture.outputs["Color"], principled.inputs["Base Color"])
                links.new(texture.outputs["Alpha"], principled.inputs["Alpha"])
            mesh.materials.append(material)
        else:
            self.report({"WARNING"}, f"Depth mesh created, but source image is missing: {image_name}")

        self.report({"INFO"}, f"Created VGGT depth mesh: {len(vertices):,} vertices, {len(faces):,} faces")
        return {"FINISHED"}


CLASSES = (
    BTS_OT_toggle_concept_scene,
    BTS_OT_submit_vggt_job,
    BTS_OT_check_vggt_job,
    BTS_OT_import_vggt_point_cloud,
    BTS_OT_create_vggt_camera,
    BTS_OT_create_vggt_floor_proxy,
    BTS_OT_create_vggt_depth_mesh,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bts_concept_scene_expanded = BoolProperty(default=False)
    bpy.types.Scene.bts_concept_input_mode = EnumProperty(
        name="Input",
        items=(
            ("SINGLE", "Single Image", "Generate a 2.5D proxy from one reference image"),
            ("FOLDER", "Image Folder", "Jointly reconstruct a scene from all supported images in a folder"),
        ),
        default="SINGLE",
    )
    bpy.types.Scene.bts_concept_image_path = StringProperty(subtype="FILE_PATH")
    bpy.types.Scene.bts_concept_image_directory = StringProperty(subtype="DIR_PATH")
    bpy.types.Scene.bts_vggt_service_url = StringProperty(default="http://127.0.0.1:8765")
    bpy.types.Scene.bts_vggt_bundle_adjustment = BoolProperty(default=False)
    bpy.types.Scene.bts_vggt_job_id = StringProperty(options={"HIDDEN"})
    bpy.types.Scene.bts_vggt_status_path = StringProperty(options={"HIDDEN"})
    bpy.types.Scene.bts_vggt_job_directory = StringProperty(options={"HIDDEN"})
    bpy.types.Scene.bts_vggt_log_tail = StringProperty(options={"HIDDEN"})
    bpy.types.Scene.bts_vggt_job_status = StringProperty(default="Service not contacted")
    bpy.types.Scene.bts_vggt_depth_mesh_stride = IntProperty(
        name="Mesh Resolution",
        description="Use every nth depth pixel; lower values create denser meshes",
        default=4,
        min=1,
        max=64,
    )
    bpy.types.Scene.bts_vggt_depth_mesh_confidence = FloatProperty(
        name="Min Confidence",
        description="Remove depth samples below this VGGT confidence",
        default=1.2,
        min=0.0,
        max=100.0,
    )
    bpy.types.Scene.bts_vggt_depth_mesh_discontinuity = FloatProperty(
        name="Depth Edge",
        description="Do not connect a face across a relative depth jump larger than this value",
        default=0.08,
        min=0.001,
        max=1.0,
    )
    bpy.types.Scene.bts_vggt_floor_image_portion = FloatProperty(name="Floor Image Portion", default=0.35, min=0.1, max=0.9)
    bpy.types.Scene.bts_vggt_floor_confidence = FloatProperty(name="Floor Min Confidence", default=1.0, min=0.0, max=100.0)
    bpy.types.Scene.bts_vggt_floor_fit_tolerance = FloatProperty(name="Floor Fit Tolerance", default=0.03, min=0.001, max=0.5)
    bpy.types.Scene.bts_vggt_floor_padding = FloatProperty(name="Floor Padding", default=0.1, min=0.0, max=1.0)


def unregister() -> None:
    for name in (
        "bts_vggt_job_status",
        "bts_vggt_job_directory",
        "bts_vggt_log_tail",
        "bts_vggt_depth_mesh_discontinuity",
        "bts_vggt_depth_mesh_confidence",
        "bts_vggt_depth_mesh_stride",
        "bts_vggt_floor_padding",
        "bts_vggt_floor_fit_tolerance",
        "bts_vggt_floor_confidence",
        "bts_vggt_floor_image_portion",
        "bts_vggt_status_path",
        "bts_vggt_job_id",
        "bts_vggt_bundle_adjustment",
        "bts_vggt_service_url",
        "bts_concept_image_directory",
        "bts_concept_image_path",
        "bts_concept_input_mode",
        "bts_concept_scene_expanded",
    ):
        delattr(bpy.types.Scene, name)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
