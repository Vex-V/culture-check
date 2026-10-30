"""Copies the example reports into a folder for the private dataset.

    python scripts/bundle.py OUT

Holds Qloo responses and ad videos, so OUT must never go in a public repository.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from culturecheck.config import settings  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1])
    data = settings().data
    samples = json.loads((data / "samples.json").read_text(encoding="utf-8"))
    tested = json.loads((data / "tested.json").read_text(encoding="utf-8"))
    ids = samples + [ad["report"] for group in tested for ad in group["ads"]]
    out.mkdir(parents=True, exist_ok=True)
    (out / "uploads").mkdir(exist_ok=True)
    shutil.copy2(data / "samples.json", out)
    shutil.copy2(data / "tested.json", out)
    for rid in ids:
        report = json.loads((data / "reports" / rid / "report.json").read_text(encoding="utf-8"))
        report.pop("appeal_noqloo", None)
        shutil.copytree(data / "reports" / rid, out / "reports" / rid, dirs_exist_ok=True)
        (out / "reports" / rid / "report.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8")
        for path in (out / "reports" / rid / "views").glob("*.json"):
            view = json.loads(path.read_text(encoding="utf-8"))
            view.pop("baseline", None)
            view.pop("compare", None)
            path.write_text(json.dumps(view, ensure_ascii=False), encoding="utf-8")
        shutil.copytree(data / "vidra" / "out" / rid, out / "vidra" / "out" / rid,
                        dirs_exist_ok=True)
        shutil.copy2(data / "uploads" / report["video"], out / "uploads")
    print(f"{len(ids)} reports in {out}")


if __name__ == "__main__":
    main()
