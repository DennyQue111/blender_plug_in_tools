# Local VGGT Scene Service

This is deliberately separate from the Blender extension. Blender's bundled Python stays clean; VGGT, PyTorch, CUDA and the model weights live in their own virtual environment.

The first version is a small local HTTP service. It accepts an absolute image path, copies the image into a per-job working directory, then runs VGGT's official `demo_colmap.py`. The output is a COLMAP-compatible reconstruction that Blender can import in a later Shelf tool.

## 1. Install VGGT in an external environment

From this directory, create and activate a normal Python 3.10+ virtual environment, then clone/install VGGT following its official instructions:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
git clone https://github.com/facebookresearch/vggt.git vendor\vggt
pip install -r vendor\vggt\requirements.txt
pip install -r requirements.txt
```

The first inference downloads the VGGT weights. Do not create this environment inside `blender_tool_shelf`; Blender must not import it.

## 2. Start the service

```powershell
.\.venv\Scripts\python.exe run_service.py
```

The launcher automatically finds either `scene_ai_service/vendor/vggt` or the project's `vendor/vggt`, uses its own virtual-environment Python, and creates `workspace` when needed. The service binds to `127.0.0.1` only: it is local to this computer and is not exposed to the network.

If VGGT is in another directory or port `8765` is occupied:

```powershell
.\.venv\Scripts\python.exe run_service.py --vggt-repo D:\AI\vggt --port 8766
```

## 3. Submit a job

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/jobs -ContentType application/json -Body '{"image_path":"E:\\images\\concept.png","bundle_adjustment":false}'
```

Check the returned `status_url`. On success, the job directory contains:

```text
workspace/jobs/<job-id>/
├─ input/images/<source image>
└─ input/sparse/           # COLMAP cameras, image poses, and points
```

`demo_colmap.py` is intentionally used rather than reimplementing VGGT model calls. This keeps the service aligned with the upstream model's supported input/output format.

## Notes

- A single concept image yields an inferred, image-facing scene proxy, not a fully known 3D world. Multiple related views are more reliable.
- `bundle_adjustment` is useful for multiple views. It is normally unnecessary for one image.
- The source image is copied, never modified.