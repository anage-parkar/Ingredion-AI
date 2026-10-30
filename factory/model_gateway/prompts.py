"""Versioned prompts.

Prompts are files under ``prompts/<agent>/<name>.v<N>.md``. The version is in the
file name, the registry returns the latest unless a version is pinned, and every
model call records ``name@vN`` plus the file's SHA-256 in the audit trail. Changing
a prompt therefore means a new file, a re-run of the evaluation set and a release
approval (the second human gate in both SOWs), never an edit in place.

Rendering is plain ``{{placeholder}}`` substitution; a missing placeholder is an
error so a renamed input cannot silently reach the model as literal braces.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

PROMPTS_ROOT = Path(__file__).resolve().parent / "prompts"
_FILE = re.compile(r"^(?P<name>[a-z0-9_]+)\.v(?P<version>\d+)\.md$")
_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


class PromptNotFound(LookupError):
    pass


class PromptRenderError(ValueError):
    pass


@dataclass(frozen=True)
class Prompt:
    name: str  # "order_intake/a3_extract"
    version: int
    text: str
    sha256: str
    path: str

    @property
    def ref(self) -> str:
        return f"{self.name}@v{self.version}"

    @property
    def placeholders(self) -> list[str]:
        seen: list[str] = []
        for match in _PLACEHOLDER.finditer(self.text):
            if match.group(1) not in seen:
                seen.append(match.group(1))
        return seen

    def render(self, **values: object) -> str:
        missing = [p for p in self.placeholders if p not in values]
        if missing:
            raise PromptRenderError(f"{self.ref}: missing values for {missing}")
        return _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), self.text)


class PromptRegistry:
    def __init__(self, root: Path | str = PROMPTS_ROOT) -> None:
        self.root = Path(root)

    def _dir_and_base(self, name: str) -> tuple[Path, str]:
        folder, _, base = name.rpartition("/")
        return (self.root / folder if folder else self.root), base

    def versions(self, name: str) -> list[int]:
        folder, base = self._dir_and_base(name)
        if not folder.is_dir():
            return []
        found: list[int] = []
        for path in folder.iterdir():
            match = _FILE.match(path.name)
            if match and match.group("name") == base:
                found.append(int(match.group("version")))
        return sorted(found)

    def get(self, name: str, version: int | None = None) -> Prompt:
        versions = self.versions(name)
        if not versions:
            raise PromptNotFound(f"no prompt files for {name!r} under {self.root}")
        if version is None:
            version = versions[-1]
        elif version not in versions:
            raise PromptNotFound(f"{name} has versions {versions}, not v{version}")
        folder, base = self._dir_and_base(name)
        path = folder / f"{base}.v{version}.md"
        text = path.read_text(encoding="utf-8")
        return Prompt(
            name=name,
            version=version,
            text=text,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            path=str(path),
        )

    def names(self) -> list[str]:
        out: set[str] = set()
        for path in self.root.rglob("*.md"):
            match = _FILE.match(path.name)
            if match:
                rel = path.parent.relative_to(self.root).as_posix()
                out.add(f"{rel}/{match.group('name')}" if rel != "." else match.group("name"))
        return sorted(out)
