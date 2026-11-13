"""Executable module entrypoint for pipeline.kinematic_ml."""
from __future__ import annotations

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
