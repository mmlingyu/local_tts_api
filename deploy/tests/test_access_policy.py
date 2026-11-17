import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from access_policy import AccessConfigError, compile_access  # noqa: E402


def test_loopback_keeps_builtin_origins_including_the_local_page():
    access = compile_access(bind_host="127.0.0.1", port=8800)
    assert access["allowedHosts"] == ["127.0.0.1:8800", "localhost:8800"]
    assert "http://127.0.0.1:8787" in access["origins"]
    assert "http://127.0.0.1:8133" in access["origins"]
    assert "http://localhost:8133" in access["origins"]
    assert access["authorization"] == "loopback-only"
    assert access["wiredIntoServer"] is True


def test_public_base_requires_a_token_and_wildcard_is_rejected():
    with pytest.raises(AccessConfigError):
        compile_access(bind_host="127.0.0.1", port=8800, public_base="https://tts.example")
    access = compile_access(
        bind_host="127.0.0.1",
        port=8800,
        public_base="https://tts.example",
        api_token="n" * 16,
        extra_origins="http://127.0.0.1:8133",
    )
    assert access["authorization"] == "bearer"
    assert "http://127.0.0.1:8133" in access["origins"]
    with pytest.raises(AccessConfigError):
        compile_access(bind_host="0.0.0.0", port=8800, api_token="n" * 16)
    with pytest.raises(AccessConfigError):
        compile_access(bind_host="127.0.0.1", port=8800, extra_origins="*")
    with pytest.raises(AccessConfigError):
        compile_access(bind_host="127.0.0.1", port=8080)


def test_draft_scripts_do_not_touch_existing_services(tmp_path: Path):
    import subprocess

    deploy = Path(__file__).resolve().parents[1]
    rollback = (deploy / "rollback-local-tts.sh").read_text(encoding="utf-8")
    install = (deploy / "install-draft.sh").read_text(encoding="utf-8")
    real = (deploy / "install-local-tts.sh").read_text(encoding="utf-8")
    assert "systemctl" not in install
    assert "local-tts-api.service" in real
    assert "3080" in real and "8080" in real
    assert 'UNIT="local-tts-api.service"' in rollback
    assert "3080" in rollback and "8080" in rollback
    assert "--apply" in rollback
    rendered = tmp_path / "render"
    completed = subprocess.run(
        [str(deploy / "install-local-tts.sh"), "--render", str(rendered), "--port", "8800"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "没有调用服务管理器" in completed.stdout
    unit = (rendered / "local-tts-api.service").read_text(encoding="utf-8")
    assert "3080" not in unit and "8080" not in unit
    assert "run-local-tts.sh" in unit
    assert "MemoryMax=2G" in unit
    env = (rendered / "local-tts-api.env").read_text(encoding="utf-8")
    assert "TTS_PORT=8800" in env
    assert "TTS_API_TOKEN=\n" in env or env.endswith("TTS_API_TOKEN=\n") or "TTS_API_TOKEN=\n" in env
