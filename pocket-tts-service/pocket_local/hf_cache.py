"""Inspect a Pocket Hugging Face cache copied from Windows.

The cache is not in git. This tool only rewrites a snapshot link when the
blob it names already exists inside the same cache. It does not download,
does not follow a link outside the cache, and does not delete blobs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_HEX = set("0123456789abcdefABCDEF")


@dataclass(frozen=True)
class CacheAction:
    path: str
    kind: str
    target: str
    blob: str | None
    applied: bool


def _blob_name(target: str) -> str | None:
    name = target.replace("\\", "/").rstrip("/").split("/")[-1]
    if len(name) < 16 or len(name) > 64 or any(ch not in _HEX for ch in name):
        return None
    return name.lower()


def _windows_target(target: str) -> bool:
    text = target.strip()
    if "\\" in text or text.startswith("//") or text.startswith("\\\\"):
        return True
    return len(text) >= 3 and text[0].isalpha() and text[1] == ":"


def _find_blob(root: Path, name: str) -> list[Path]:
    matches: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        dirnames[:] = [item for item in dirnames if not (base / item).is_symlink()]
        if "blobs" not in base.parts:
            continue
        for filename in filenames:
            path = base / filename
            if path.is_symlink():
                continue
            if filename.lower() == name and path.is_file():
                matches.append(path)
    return matches


def _pointer_text(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file():
        return None
    if path.stat().st_size > 512:
        return None
    raw = path.read_bytes()
    if b"\x00" in raw or b"\n" in raw.strip():
        return None
    text = raw.decode("utf-8", errors="replace").strip()
    if _blob_name(text) is None:
        return None
    if not (_windows_target(text) or text.startswith("..") or text.startswith("/")):
        return None
    return text


def _classify(root: Path, path: Path, target: str) -> CacheAction | None:
    del root
    blob = _blob_name(target)
    relative_and_present = path.is_symlink() and not os.path.isabs(target) and not _windows_target(target) and path.exists()
    if relative_and_present:
        return None
    kind = "windows-link" if _windows_target(target) else "outside-link"
    if blob is None:
        kind = "unrecognized-link"
    return CacheAction(str(path), kind, target, blob, False)


def plan(root: Path) -> list[CacheAction]:
    root = root.resolve()
    actions: list[CacheAction] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        for name in list(dirnames):
            path = base / name
            if path.is_symlink():
                action = _classify(root, path, os.readlink(path))
                if action is not None:
                    actions.append(action)
                dirnames.remove(name)
        for name in filenames:
            path = base / name
            if path.is_symlink():
                action = _classify(root, path, os.readlink(path))
                if action is not None:
                    actions.append(action)
                continue
            text = _pointer_text(path)
            if text is not None:
                action = _classify(root, path, text)
                if action is not None:
                    actions.append(action)
    return actions


def apply_plan(root: Path, actions: list[CacheAction] | None = None) -> list[CacheAction]:
    root = root.resolve()
    chosen = plan(root) if actions is None else actions
    done: list[CacheAction] = []
    for action in chosen:
        if action.blob is None:
            done.append(action)
            continue
        matches = _find_blob(root, action.blob)
        if len(matches) != 1:
            done.append(action)
            continue
        link = Path(action.path)
        if root not in link.resolve().parents and link.resolve() != root:
            # The link itself must stay inside the cache even when its target does not.
            try:
                link_parent = link.parent.resolve()
            except OSError:
                done.append(action)
                continue
            if root != link_parent and root not in link_parent.parents:
                done.append(action)
                continue
        relative = os.path.relpath(matches[0], start=link.parent)
        if relative.startswith("../") and root not in matches[0].parents:
            done.append(action)
            continue
        link.unlink()
        link.symlink_to(relative)
        done.append(CacheAction(action.path, action.kind, relative, action.blob, True))
    return done
