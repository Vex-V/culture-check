"""The example reports, copied from the image into the writable data folder.

They hold Qloo's responses, so they are in the deployment and never in the repo.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from .config import settings

log = logging.getLogger("culturecheck.seed")


def seed() -> None:
    source = os.environ.get("CC_SEED_DIR")
    if source and Path(source).is_dir() and not (settings().data / "samples.json").exists():
        shutil.copytree(source, settings().data, dirs_exist_ok=True)
        log.info("examples copied from %s", source)
