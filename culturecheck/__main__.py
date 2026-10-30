"""`culturecheck` / `python -m culturecheck`: serve the app.

    culturecheck [--host 0.0.0.0] [--port 8000]
"""

from __future__ import annotations

import argparse
import logging
import os


def main() -> None:
    ap = argparse.ArgumentParser(prog="culturecheck")
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    import uvicorn

    from .seed import seed

    seed()
    uvicorn.run("culturecheck.app:app", host=a.host, port=a.port, workers=1,
                proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
