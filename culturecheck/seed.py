"""Fills an empty data folder with the example reports.

The hosted app starts with no data, and Qloo's responses may not sit in a public
repository, so the examples live in a private dataset named by `CC_SEED_DATASET`.
"""

from __future__ import annotations

import logging
import os

from .config import settings

log = logging.getLogger("culturecheck.seed")


def seed() -> None:
    repo = os.environ.get("CC_SEED_DATASET")
    if not repo or (settings().data / "samples.json").exists():
        return
    from huggingface_hub import snapshot_download

    try:
        snapshot_download(repo, repo_type="dataset", local_dir=settings().data,
                          token=os.environ.get("HF_TOKEN"))
        log.info("examples loaded from %s", repo)
    except Exception:                                     # noqa: BLE001
        log.exception("could not load the examples; uploads still work")
