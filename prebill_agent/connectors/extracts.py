"""Extract landing (redline v2): sources with no read interface deliver scheduled
extracts to a Cloud Storage bucket; the agent reads the latest file per source.

Files are CSV named ``<source>/<anything>.csv``; the newest object per source wins.
``LocalExtractLanding`` reads the same layout from a folder for Dev and tests;
``GcsExtractLanding`` reads the bucket through ``google-cloud-storage`` (lazy import).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Protocol


class ExtractLanding(Protocol):
    def latest(self, source: str) -> list[dict[str, str]]: ...


def _parse_csv(text: str) -> list[dict[str, str]]:
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


class LocalExtractLanding:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def latest(self, source: str) -> list[dict[str, str]]:
        folder = self.root / source
        if not folder.is_dir():
            return []
        files = sorted(folder.glob("*.csv"), key=lambda p: p.stat().st_mtime)
        return _parse_csv(files[-1].read_text(encoding="utf-8")) if files else []


class GcsExtractLanding:
    def __init__(self, bucket: str, *, client: Any = None) -> None:
        self.bucket_name = bucket
        self._client = client

    def _bucket(self) -> Any:
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client()
        return self._client.bucket(self.bucket_name)

    def latest(self, source: str) -> list[dict[str, str]]:
        blobs = [b for b in self._bucket().list_blobs(prefix=f"{source}/") if b.name.endswith(".csv")]
        if not blobs:
            return []
        newest = max(blobs, key=lambda b: b.updated or 0)
        return _parse_csv(newest.download_as_text())
