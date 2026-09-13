"""Local task service that runs VGGT and exports Blender-friendly scene data."""

from __future__ import annotations

import shutil
import subprocess
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from settings import Settings, load_settings


app = FastAPI(title="Local VGGT Scene Service", version="0.1.0")
SETTINGS = load_settings()
JOBS: dict[str, "Job"] = {}


class CreateJobRequest(BaseModel):
    image_paths: list[Path] = Field(min_length=1, description="Absolute paths to one scene's reference images")
    bundle_adjustment: bool = Field(default=False)


@dataclass
class Job:
    id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    directory: str
    bundle_adjustment: bool
    error: str | None = None


def _read_log_tail(job: Job, line_count: int = 12) -> str:
    log_path = Path(job.directory) / "vggt.log"
    if not log_path.is_file():
        return "Waiting for VGGT process to start..."
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-line_count:])
    except OSError as exc:
        return f"Could not read log: {exc}"


def _run_job(job_id: str, sources: list[Path], settings: Settings) -> None:
    job = JOBS[job_id]
    job.status = "running"
    job_dir = Path(job.directory)
    image_dir = job_dir / "input" / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    for index, source in enumerate(sources):
        destination_name = source.name
        if destination_name.casefold() in used_names:
            destination_name = f"{index:03d}_{destination_name}"
        used_names.add(destination_name.casefold())
        shutil.copy2(source, image_dir / destination_name)

    command = [
        str(settings.python_executable),
        "-u",
        str(Path(__file__).with_name("run_vggt_scene.py")),
        f"--scene-dir={job_dir / 'input'}",
    ]
    log_path = job_dir / "vggt.log"
    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            subprocess.run(
                command,
                cwd=settings.vggt_repository,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=settings.job_timeout_seconds,
            )
        output_dir = job_dir / "input" / "scene_data"
        if not output_dir.exists():
            raise RuntimeError("VGGT finished without creating the scene_data output directory")
        job.status = "succeeded"
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "vggt_repository": str(SETTINGS.vggt_repository)}


@app.post("/jobs", status_code=202)
def create_job(request: CreateJobRequest) -> dict[str, str]:
    sources = [image_path.expanduser().resolve() for image_path in request.image_paths]
    if any(not source.is_file() for source in sources):
        raise HTTPException(status_code=400, detail="Every image_paths entry must be an existing file")

    job_id = uuid.uuid4().hex
    job_dir = SETTINGS.workspace / "jobs" / job_id
    job_dir.mkdir(parents=True)
    JOBS[job_id] = Job(
        id=job_id,
        status="queued",
        directory=str(job_dir),
        bundle_adjustment=request.bundle_adjustment,
    )
    thread = threading.Thread(target=_run_job, args=(job_id, sources, SETTINGS), daemon=True)
    thread.start()
    return {"job_id": job_id, "status_url": f"/jobs/{job_id}"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    response = asdict(job)
    response["log_tail"] = _read_log_tail(job)
    return response
