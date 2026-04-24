from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn

from mediacovergenerator.runtime import run_once


def main() -> None:
    parser = argparse.ArgumentParser(description="MediaCoverGenerator")
    parser.add_argument("--run-once", action="store_true", help="Run cover generation once using the saved config, then exit")
    args = parser.parse_args()

    if args.run_once:
        project_root = Path(__file__).resolve().parent.parent
        raise SystemExit(run_once(project_root))

    host = os.getenv("MCG_HOST", "0.0.0.0")
    port = int(os.getenv("MCG_PORT", "38100"))
    uvicorn.run("mediacovergenerator.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
