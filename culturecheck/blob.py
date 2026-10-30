"""Vercel Blob, as the way a large upload reaches the app.

Vercel refuses a request over 4.5 MB, so the page sends the video straight to a Blob store
with a short-lived token from here. The store is private: only the app can read it, and it
fetches the video and deletes it at once, so a video stays there for seconds.

Running elsewhere needs none of this: with no BLOB_READ_WRITE_TOKEN the page posts the file.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

API = "https://vercel.com/api/blob"
API_VERSION = "12"
TOKEN_S = 600


def _token() -> str:
    return os.environ.get("BLOB_READ_WRITE_TOKEN", "")


def enabled() -> bool:
    return bool(_token())


def _store() -> str:
    """The store id: a read-write token is `vercel_blob_rw_<store>_<secret>`."""
    return _token().split("_")[3]


def client_token(pathname: str, max_bytes: int) -> str:
    """What the page may upload: this one path, up to this size, for a few minutes."""
    payload = base64.b64encode(json.dumps({
        "pathname": pathname, "maximumSizeInBytes": max_bytes, "addRandomSuffix": True,
        "validUntil": int((time.time() + TOKEN_S) * 1000)},
        separators=(",", ":")).encode()).decode()     # Blob refuses a token with spaces
    signed = hmac.new(_token().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"vercel_blob_client_{_store()}_" + base64.b64encode(
        f"{signed}.{payload}".encode()).decode()


def ours(url: str) -> bool:
    """Whether a URL is in this store: the app fetches only what it handed out."""
    host = urlparse(url).hostname or ""
    return url.startswith("https://") and host.lower() == (
        f"{_store()}.private.blob.vercel-storage.com".lower())


async def fetch(url: str, dest: Path, max_bytes: int) -> bool:
    """Writes the blob to `dest`; False when it is longer than `max_bytes`."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    headers = {"authorization": f"Bearer {_token()}"}
    async with httpx.AsyncClient(timeout=60) as client, client.stream(
            "GET", url, headers=headers) as r:
        r.raise_for_status()
        with dest.open("wb") as out:
            async for chunk in r.aiter_bytes(1 << 20):
                size += len(chunk)
                if size > max_bytes:
                    return False
                out.write(chunk)
    return True


async def delete(url: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{API}/delete", json={"urls": [url]},
                              headers={"authorization": f"Bearer {_token()}",
                                       "x-api-version": API_VERSION})
        r.raise_for_status()
