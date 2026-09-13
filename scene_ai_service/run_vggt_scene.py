"""Run VGGT and export Blender-friendly scene data without PyCOLMAP."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import torch
import torch.nn.functional as functional
import trimesh
from PIL import Image

repository = Path(os.environ["VGGT_REPO"]).resolve()
if not (repository / "vggt").is_dir():
    raise RuntimeError(f"VGGT_REPO does not contain the vggt package: {repository}")
sys.path.insert(0, str(repository))

from vggt.models.vggt import VGGT
from vggt.utils.geometry import unproject_depth_map_to_point_map
from vggt.utils.load_fn import load_and_preprocess_images_square
from vggt.utils.pose_enc import pose_encoding_to_extri_intri


MODEL_URL = "https://huggingface.co/facebook/VGGT-1B/resolve/main/model.pt"
MODEL_FILENAME = "model.pt"
INFERENCE_SIZE = 518
MAX_POINT_COUNT = 100_000
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
DOWNLOAD_RETRY_DELAY_SECONDS = 5
CONFIDENCE_THRESHOLD = 1.2
MINIMUM_EXPORTED_POINT_COUNT = 1_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-dir", type=Path, required=True)
    return parser.parse_args()


def _find_images(image_directory: Path) -> list[Path]:
    supported = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
    images = sorted(path for path in image_directory.iterdir() if path.suffix.lower() in supported)
    if not images:
        raise ValueError(f"No supported images found in {image_directory}")
    return images


def _save_depth_preview(depth: np.ndarray, destination: Path) -> None:
    preview = depth.astype(np.float32)
    valid = np.isfinite(preview) & (preview > 0)
    normalized = np.zeros_like(preview)
    if np.any(valid):
        inverse_depth = 1.0 / preview[valid]
        low, high = np.percentile(inverse_depth, (1, 99))
        normalized[valid] = np.clip((inverse_depth - low) / max(high - low, 1e-8), 0, 1)
    Image.fromarray((normalized * 255).astype(np.uint8), mode="L").save(destination)


def _sample_points(points: np.ndarray, colors: np.ndarray, confidence: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(points).all(axis=1) & np.isfinite(confidence)
    mask = valid & (confidence > CONFIDENCE_THRESHOLD)
    if mask.sum() < MINIMUM_EXPORTED_POINT_COUNT and valid.any():
        # VGGT's own tracking helper uses 1.2 as its low-confidence cutoff.
        # Single images can still be conservative, so retain the most confident
        # valid quarter instead of exporting an empty PLY that Blender cannot import.
        fallback_threshold = np.percentile(confidence[valid], 75)
        mask = valid & (confidence >= fallback_threshold)
        print(
            "Only "
            f"{int((valid & (confidence > CONFIDENCE_THRESHOLD)).sum()):,} points exceeded "
            f"the confidence threshold; using the top-confidence fallback at "
            f"{fallback_threshold:.3f}"
        )
    points, colors = points[mask], colors[mask]
    if len(points) > MAX_POINT_COUNT:
        indices = np.linspace(0, len(points) - 1, MAX_POINT_COUNT, dtype=np.int64)
        points, colors = points[indices], colors[indices]
    return points, colors


def _model_paths() -> tuple[Path, Path, Path]:
    cache_directory = Path(__file__).with_name("model_cache") / "VGGT-1B"
    complete_path = cache_directory / MODEL_FILENAME
    partial_path = cache_directory / f"{MODEL_FILENAME}.part"
    legacy_path = Path(torch.hub.get_dir()) / "checkpoints" / MODEL_FILENAME
    return complete_path, partial_path, legacy_path


def _download_model_weights() -> Path:
    """Download model weights with HTTP Range support and atomic completion.

    A previous torch.hub attempt saves an interrupted download as ``model.pt``.
    Move that file into this downloader's ``.part`` location so its valid prefix
    can be retained rather than downloading it again from byte zero.
    """

    complete_path, partial_path, legacy_path = _model_paths()
    complete_path.parent.mkdir(parents=True, exist_ok=True)
    if complete_path.is_file():
        return complete_path
    if not partial_path.exists() and legacy_path.is_file():
        print(f"Migrating resumable Torch cache: {legacy_path}")
        shutil.move(legacy_path, partial_path)

    total: int | None = None
    while True:
        offset = partial_path.stat().st_size if partial_path.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        request = Request(MODEL_URL, headers=headers)
        print(f"Downloading VGGT weights to {partial_path} (resuming at {offset:,} bytes)")
        try:
            with urlopen(request, timeout=60) as response:
                status = getattr(response, "status", response.getcode())
                if offset and status != 206:
                    print("Server did not accept the range request; restarting the partial download")
                    offset = 0
                mode = "ab" if offset else "wb"
                content_range = response.headers.get("Content-Range", "")
                content_length = int(response.headers.get("Content-Length", "0"))
                if "/" in content_range and content_range.rsplit("/", 1)[1].isdigit():
                    total = int(content_range.rsplit("/", 1)[1])
                elif content_length:
                    total = offset + content_length
                downloaded = offset
                with partial_path.open(mode) as output:
                    while chunk := response.read(DOWNLOAD_CHUNK_SIZE):
                        output.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            print(
                                f"Downloaded {downloaded / 1024**3:.2f} / {total / 1024**3:.2f} GiB",
                                end="\r",
                            )
            print()
        except OSError as exc:
            print(f"Weight download connection interrupted: {exc}")

        current_size = partial_path.stat().st_size if partial_path.exists() else 0
        if total and current_size == total:
            partial_path.replace(complete_path)
            return complete_path
        expected = f" of {total:,} bytes" if total else ""
        print(
            f"Weight download paused at {current_size:,}{expected}; retrying in "
            f"{DOWNLOAD_RETRY_DELAY_SECONDS} seconds"
        )
        time.sleep(DOWNLOAD_RETRY_DELAY_SECONDS)


def main() -> None:
    args = parse_args()
    scene_directory = args.scene_dir.resolve()
    image_paths = _find_images(scene_directory / "images")
    output_directory = scene_directory / "scene_data"
    output_directory.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.bfloat16 if device.type == "cuda" and torch.cuda.get_device_capability()[0] >= 8 else torch.float16
    print(f"Using device: {device}")
    print(f"Loading VGGT model from {MODEL_URL}")
    model = VGGT()
    model_path = _download_model_weights()
    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
    model.eval()
    if device.type == "cuda":
        model.half()
    model.to(device)

    images, original_coordinates = load_and_preprocess_images_square(image_paths, 1024)
    images = images.to(device)
    inference_images = functional.interpolate(
        images, size=(INFERENCE_SIZE, INFERENCE_SIZE), mode="bilinear", align_corners=False
    )
    autocast = torch.cuda.amp.autocast(dtype=dtype) if device.type == "cuda" else nullcontext()
    with torch.no_grad(), autocast:
        batch = inference_images[None]
        tokens, patch_indices = model.aggregator(batch)
        pose_encoding = model.camera_head(tokens)[-1]
        extrinsics, intrinsics = pose_encoding_to_extri_intri(pose_encoding, batch.shape[-2:])
        depth, confidence = model.depth_head(tokens, batch, patch_indices)

    extrinsics = extrinsics.squeeze(0).cpu().numpy()
    intrinsics = intrinsics.squeeze(0).cpu().numpy()
    depth = depth.squeeze(0).cpu().numpy()
    confidence = confidence.squeeze(0).cpu().numpy()
    points = unproject_depth_map_to_point_map(depth, extrinsics, intrinsics)
    colors = (inference_images.cpu().numpy().transpose(0, 2, 3, 1) * 255).astype(np.uint8)

    flat_points, flat_colors = _sample_points(points.reshape(-1, 3), colors.reshape(-1, 3), confidence.reshape(-1))
    trimesh.PointCloud(flat_points, colors=flat_colors).export(output_directory / "points.ply")
    np.save(output_directory / "depth.npy", depth)
    np.save(output_directory / "confidence.npy", confidence)
    _save_depth_preview(depth[0].squeeze(), output_directory / "depth_preview.png")
    (output_directory / "cameras.json").write_text(
        json.dumps(
            {
                "coordinate_convention": "OpenCV world_to_camera",
                "inference_resolution": [INFERENCE_SIZE, INFERENCE_SIZE],
                "images": [path.name for path in image_paths],
                "extrinsics_world_to_camera": extrinsics.tolist(),
                "intrinsics": intrinsics.tolist(),
                "original_image_coordinates": original_coordinates.cpu().numpy().tolist(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved {len(flat_points):,} points to {output_directory / 'points.ply'}")


if __name__ == "__main__":
    main()
