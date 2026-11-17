import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from access_policy import AccessConfigError, compile_access  # noqa: E402


def test_loopback_keeps_builtin_origins_and_does_not_claim_to_be_wired():
    access = compile_access(bind_host="127.0.0.1", port=8800)
    assert access["allowedHosts"] == ["127.0.0.1:8800", "localhost:8800"]
    assert "http://127.0.0.1:8787" in access["origins"]
    assert access["authorization"] == "loopback-only"
    assert access["wiredIntoServer"] is False


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


def test_draft_scripts_do_not_touch_existing_services():
    deploy = Path(__file__).resolve().parents[1]
    rollback = (deploy / "rollback-local-tts.sh").read_text(encoding="utf-8")
    install = (deploy / "install-draft.sh").read_text(encoding="utf-8")
    assert "systemctl" not in install
    assert 'UNIT="local-tts-api.service"' in rollback
    assert "3080" in rollback and "8080" in rollback
    assert "--apply" in rollback
