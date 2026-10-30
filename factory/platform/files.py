"""Files the pipeline lands in Cloud Storage (PO attachments, contracts, rate files).

Gold rows carry a ``file_uri`` and a ``sha256``; the agents fetch the object by
pointer and verify the hash, and never keep a copy outside the evidence store.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Protocol


class FileError(RuntimeError):
    pass


class IntegrityError(FileError):
    """The object's content does not match the hash recorded on the gold row."""


class FileStore(Protocol):
    name: str

    def get(self, uri: str) -> bytes: ...


class InMemoryFileStore:
    name = "memory"

    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files: dict[str, bytes] = dict(files or {})

    def put(self, uri: str, content: bytes) -> str:
        self.files[uri] = content
        return uri

    def get(self, uri: str) -> bytes:
        try:
            return self.files[uri]
        except KeyError:
            raise FileError(f"no file at {uri}") from None


class LocalFileStore:
    """``file://`` URIs or paths relative to ``root`` (Dev)."""

    name = "local"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def get(self, uri: str) -> bytes:
        path = Path(uri[7:]) if uri.startswith("file://") else self.root / uri
        if not path.is_file():
            raise FileError(f"no file at {uri}")
        return path.read_bytes()


class GcsFileStore:
    name = "gcs"

    def __init__(self, *, client: Any = None) -> None:
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client()
        return self._client

    def get(self, uri: str) -> bytes:
        if not uri.startswith("gs://"):
            raise FileError(f"not a Cloud Storage URI: {uri}")
        bucket, _, path = uri[5:].partition("/")
        blob = self._get_client().bucket(bucket).blob(path)
        try:
            return blob.download_as_bytes()
        except Exception as exc:
            raise FileError(f"could not read {uri}: {exc.__class__.__name__}") from exc


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def fetch_verified(store: FileStore, uri: str, sha256: str | None) -> bytes:
    """Read the object and check it against the hash on the gold row (when present)."""
    content = store.get(uri)
    if sha256 and sha256_hex(content).lower() != sha256.lower():
        raise IntegrityError(f"{uri}: content hash does not match the gold row")
    return content


__all__ = ["FileError", "FileStore", "GcsFileStore", "InMemoryFileStore", "IntegrityError", "LocalFileStore", "fetch_verified", "sha256_hex"]
