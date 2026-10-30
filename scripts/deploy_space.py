"""Publishes the app to a Hugging Face Space and the examples to a private dataset.

    hf auth login
    python scripts/bundle.py BUNDLE
    python scripts/deploy_space.py BUNDLE

Sets no secrets. Add OPENAI_API_KEY, QLOO_API_KEY and HF_TOKEN in the Space's settings.
"""

from __future__ import annotations

import sys
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
CODE = ["Dockerfile", ".dockerignore", "LICENSE", "pyproject.toml", "culturecheck/**", "vidra/**"]


def main() -> None:
    api = HfApi()
    user = api.whoami()["name"]
    space, dataset = f"{user}/culture-check", f"{user}/culture-check-data"

    api.create_repo(dataset, repo_type="dataset", private=True, exist_ok=True)
    api.upload_folder(repo_id=dataset, repo_type="dataset", folder_path=sys.argv[1])

    api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True)
    api.upload_folder(repo_id=space, repo_type="space", folder_path=ROOT, allow_patterns=CODE,
                      ignore_patterns=["**/__pycache__/**", "*.pyc"])
    api.upload_file(repo_id=space, repo_type="space", path_in_repo="README.md",
                    path_or_fileobj=ROOT / "deploy" / "space.md")
    for key, value in (("CC_SEED_DATASET", dataset), ("CC_VLM", "gpt-5.4-mini"),
                       ("CC_LLM", "gpt-5.4-mini")):
        api.add_space_variable(space, key, value)
    print(f"https://huggingface.co/spaces/{space}")


if __name__ == "__main__":
    main()
