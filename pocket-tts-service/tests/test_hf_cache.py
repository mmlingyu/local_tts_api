from pathlib import Path

from pocket_local.hf_cache import apply_plan, plan


BLOB = "a" * 40


def test_windows_link_is_rewritten_only_to_the_local_blob(tmp_path: Path):
    root = tmp_path / "hf-home"
    blob = root / "hub" / "models--kyutai--pocket-tts" / "blobs" / BLOB
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"weights")
    link = root / "hub" / "models--kyutai--pocket-tts" / "snapshots" / "rev" / "model.safetensors"
    link.parent.mkdir(parents=True)
    link.symlink_to(f"D:\\aispace\\pocket\\blobs\\{BLOB}")
    actions = plan(root)
    assert len(actions) == 1
    assert actions[0].applied is False
    assert actions[0].kind == "windows-link"
    done = apply_plan(root, actions)
    assert done[0].applied is True
    assert link.is_symlink()
    assert link.read_bytes() == b"weights"
    assert "D:" not in os_readlink(link)


def test_text_pointer_and_escape_are_not_followed_outside(tmp_path: Path):
    root = tmp_path / "hf-home"
    blob = root / "blobs" / BLOB
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"ok")
    pointer = root / "snapshots" / "file.safetensors"
    pointer.parent.mkdir()
    pointer.write_text(f"..\\..\\blobs\\{BLOB}", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    escaped = root / "escape"
    escaped.symlink_to(outside)
    done = apply_plan(root)
    assert pointer.is_symlink()
    assert pointer.read_bytes() == b"ok"
    assert escaped.is_symlink()
    assert any(item.path.endswith("escape") and item.applied is False for item in done)


def test_two_blobs_with_the_same_name_are_left_alone(tmp_path: Path):
    root = tmp_path / "hf-home"
    for folder in ("one", "two"):
        path = root / folder / "blobs" / BLOB
        path.parent.mkdir(parents=True)
        path.write_bytes(folder.encode())
    link = root / "link"
    link.symlink_to(f"C:\\cache\\blobs\\{BLOB}")
    done = apply_plan(root)
    assert done[0].applied is False
    assert os_readlink(link).startswith("C:")


def os_readlink(path: Path) -> str:
    return str(path.readlink())
