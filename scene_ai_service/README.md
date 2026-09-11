# Local VGGT Scene Service

This is deliberately separate from the Blender extension. Blender's bundled Python stays clean; VGGT, PyTorch, CUDA and the model weights live in their own virtual environment.

The first version is a small local HTTP service. It accepts an absolute image path, copies the image into a per-job working directory, then runs VGGT directly. It writes a Blender-friendly point cloud, depth data, and camera JSON without requiring PyCOLMAP.

## 1. Install VGGT in an external environment

From the project root, create and activate a normal Python 3.10+ virtual environment, then clone/install VGGT and its COLMAP-demo dependencies:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
git clone https://github.com/facebookresearch/vggt.git vendor\vggt
python -m pip install -r .\vendor\vggt\requirements.txt
python -m pip install -r .\scene_ai_service\requirements.txt
```

The first inference downloads the VGGT weights. Do not create this environment inside `blender_tool_shelf`; Blender must not import it.

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
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/jobs -ContentType application/json -Body '{"image_path":"E:\\images\\concept.png","bundle_adjustment":false}'
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

## Notes

- A single concept image yields an inferred, image-facing scene proxy, not a fully known 3D world. Multiple related views are more reliable.
- `bundle_adjustment` is useful for multiple views. It is normally unnecessary for one image.
- The source image is copied, never modified.