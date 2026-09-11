"""One-command launcher for the local VGGT scene service."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import uvicorn


def main() -> None:
    service_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Start the local VGGT scene service")
    parser.add_argument("--vggt-repo", type=Path, default=service_root / "vendor" / "vggt")
    parser.add_argument("--workspace", type=Path, default=service_root / "workspace")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    repository = args.vggt_repo.resolve()
    if not (repository / "demo_colmap.py").is_file():
        parser.error(f"VGGT repository not found: {repository}")

    os.environ["VGGT_REPO"] = str(repository)
    os.environ["VGGT_PYTHON"] = str(Path(sys.executable).resolve())
    os.environ["VGGT_WORKSPACE"] = str(args.workspace.resolve())

    uvicorn.run("app:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()