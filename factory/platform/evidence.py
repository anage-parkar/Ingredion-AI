"""Evidence the agents keep per case: the text a model saw, its raw answer and the
guard verdicts, the payload that went to SAP, the snapshot of the records a
pre-bill verdict was computed from. One object per artefact, under
``<case id>/<run id>/<step>/<name>``, in the agent's own bucket
(``ingredion-agent-a|b-evidence-<env>``). Retention per the SOW 5.3 categories is a
bucket lifecycle rule, not code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

JSON = "application/json"


def to_bytes(content: Any, content_type: str) -> bytes:
    if isinstance(content, bytes):
        return content
    if isinstance(content, str):
        return content.encode("utf-8")
    if content_type == JSON:
        return json.dumps(content, default=_json_default, ensure_ascii=False, indent=1).encode("utf-8")
    return str(content).encode("utf-8")


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, (set, tuple)):
        return list(value)
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    return str(value)


def object_name(case_id: str, name: str, run_id: str | None = None) -> str:
    safe_case = case_id.replace("/", "_")
    return f"{safe_case}/{run_id}/{name}" if run_id else f"{safe_case}/{name}"


class EvidenceStore(Protocol):
    name: str

    def put(self, case_id: str, name: str, content: Any, *, content_type: str = JSON, run_id: str | None = None) -> str:
        """Store the artefact and return its URI."""
        ...


class InMemoryEvidenceStore:
    name = "memory"

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put(self, case_id: str, name: str, content: Any, *, content_type: str = JSON, run_id: str | None = None) -> str:
        uri = f"memory://evidence/{object_name(case_id, name, run_id)}"
        self.objects[uri] = (to_bytes(content, content_type), content_type)
        return uri

    def names(self, case_id: str) -> list[str]:
        prefix = f"memory://evidence/{case_id.replace('/', '_')}/"
        return sorted(uri[len(prefix):].split("/", 1)[-1] for uri in self.objects if uri.startswith(prefix))

    def read_json(self, uri: str) -> Any:
        return json.loads(self.objects[uri][0])


class LocalEvidenceStore:
    name = "local"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def put(self, case_id: str, name: str, content: Any, *, content_type: str = JSON, run_id: str | None = None) -> str:
        path = self.root / object_name(case_id, name, run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(to_bytes(content, content_type))
        return path.resolve().as_uri()


class GcsEvidenceStore:
    name = "gcs"

    def __init__(self, bucket: str, *, prefix: str = "", client: Any = None) -> None:
        if not bucket:
            raise ValueError("GcsEvidenceStore needs a bucket name")
        self.bucket_name = bucket
        self.prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        self._client = client

    def _bucket(self) -> Any:
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client()
        return self._client.bucket(self.bucket_name)

    def put(self, case_id: str, name: str, content: Any, *, content_type: str = JSON, run_id: str | None = None) -> str:
        path = self.prefix + object_name(case_id, name, run_id)
        blob = self._bucket().blob(path)
        blob.upload_from_string(to_bytes(content, content_type), content_type=content_type)
        return f"gs://{self.bucket_name}/{path}"


__all__ = ["JSON", "EvidenceStore", "GcsEvidenceStore", "InMemoryEvidenceStore", "LocalEvidenceStore", "object_name", "to_bytes"]
