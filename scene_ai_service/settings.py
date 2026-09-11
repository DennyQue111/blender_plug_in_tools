"""Configuration for the local VGGT process; no Blender dependency."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    vggt_repository: Path
    python_executable: Path
    workspace: Path
    job_timeout_seconds: int = 3600


def _required_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Set the {name} environment variable before starting the service")
    path = Path(value).expanduser().resolve()
    if not path.exists():
        raise RuntimeError(f"{name} does not exist: {path}")
    return path


def load_settings() -> Settings:
    repository = _required_path("VGGT_REPO")
    demo = repository / "demo_colmap.py"
    if not demo.is_file():
        raise RuntimeError(f"VGGT_REPO is missing demo_colmap.py: {repository}")
    workspace_value = os.environ.get("VGGT_WORKSPACE", "workspace")
    workspace = Path(workspace_value).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    return Settings(
        vggt_repository=repository,
        python_executable=Path(os.environ.get("VGGT_PYTHON", sys.executable)).resolve(),
        workspace=workspace,
    )