# Local VGGT Scene Service

This is deliberately separate from the Blender extension. Blender's bundled Python stays clean; VGGT, PyTorch, CUDA and the model weights live in their own virtual environment.

The first version is a small local HTTP service. It accepts one image or a list of images from the
same scene, copies them into a per-job working directory, then runs VGGT jointly. It writes a
Blender-friendly point cloud, depth data, and camera JSON without requiring PyCOLMAP.

## 1. Install VGGT in an external environment

For the maintained Windows setup, run `.\setup_scene_ai.ps1` from the project root instead. The manual steps below are retained for reference.

From the project root, create and activate a normal Python 3.10+ virtual environment, then clone/install VGGT and its COLMAP-demo dependencies:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
git clone https://github.com/facebookresearch/vggt.git vendor\vggt
python -m pip install -r .\vendor\vggt\requirements.txt
python -m pip install -r .\scene_ai_service\requirements.txt
```

The first inference downloads the VGGT weights (about 4.7 GB). The service stores an incomplete
download as `scene_ai_service/model_cache/VGGT-1B/model.pt.part` and keeps retrying HTTP Range
requests until it completes; only a complete file is renamed to `model.pt`. It also migrates an
older interrupted Torch cache on its first run. Do not create this environment inside
`blender_tool_shelf`; Blender must not import it.

For RTX 50-series GPUs, run the setup script with its default `cu128` option. It installs PyTorch
2.7 plus its matching CUDA 12.8 runtime wheels, which support the RTX 50-series `sm_120`
architecture. The older `cu121` option is retained only for older GPUs.

## 2. Start the service

```powershell
.\.venv\Scripts\python.exe .\scene_ai_service\run_service.py
```

The launcher automatically finds either `scene_ai_service/vendor/vggt` or the project's `vendor/vggt`, uses its own virtual-environment Python, and creates `workspace` when needed. The service binds to `127.0.0.1` only: it is local to this computer and is not exposed to the network.

If VGGT is in another directory or port `8765` is occupied:

```powershell
.\.venv\Scripts\python.exe .\scene_ai_service\run_service.py --vggt-repo D:\AI\vggt --port 8766
```

## 3. Submit a job

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/jobs -ContentType application/json -Body '{"image_paths":["E:\\images\\scene\\000.png","E:\\images\\scene\\045.png"],"bundle_adjustment":false}'
```

Check the returned `status_url`. On success, the job directory contains:

```text
workspace/jobs/<job-id>/
├─ input/images/<source image>
└─ input/scene_data/
   ├─ points.ply           # Blender-importable colored point cloud
   ├─ depth.npy            # Raw inferred depth values
   ├─ depth_preview.png    # Human-readable depth preview
   └─ cameras.json         # VGGT camera matrices and input metadata
```

The service uses VGGT's public model, camera, depth, and unprojection APIs, but writes its own output contract so the Windows-only PyCOLMAP wheel is not in the runtime path.

In Blender, a completed job can be imported either as the raw point cloud or as a **VGGT Depth
Mesh**. The latter reads the saved depth, confidence, camera data, and source image to create a
textured 2.5D mesh. It deliberately cuts faces across large depth discontinuities, so it is a
reference/proxy for further procedural modeling rather than a closed reconstruction.

## Notes

- A single concept image yields an inferred, image-facing scene proxy, not a fully known 3D world. Multiple related views are more reliable.
- For multi-view input, use only images of the same static scene and ensure adjacent images overlap substantially. VGGT uses image content rather than filenames to infer the geometric relationships; filenames are sorted only to make jobs reproducible and easier to inspect.
- `bundle_adjustment` is useful for multiple views. It is normally unnecessary for one image.
- The source image is copied, never modified.
