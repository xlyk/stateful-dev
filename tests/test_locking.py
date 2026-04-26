import pytest

from stateful_dev.locking import (
    FreshLockError,
    acquire_lock,
    release_lock,
    write_json_atomic,
)


def test_acquire_lock_refuses_fresh_existing_lock(tmp_path):
    lock = acquire_lock(tmp_path, run_id="run-1", timeout_minutes=60)

    try:
        with pytest.raises(FreshLockError, match="run-1"):
            acquire_lock(tmp_path, run_id="run-2", timeout_minutes=60)
    finally:
        release_lock(lock)


def test_write_json_atomic_uses_sibling_temp_file_and_replace(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "state.json"
    calls = []
    original_replace = type(target).replace

    def spy_replace(self, target_path):
        calls.append((self, target_path))
        return original_replace(self, target_path)

    monkeypatch.setattr(type(target), "replace", spy_replace)

    write_json_atomic(target, {"ok": True})

    assert target.read_text(encoding="utf-8") == '{\n  "ok": true\n}\n'
    assert calls == [(tmp_path / "nested" / "state.json.tmp", target)]
    assert not (tmp_path / "nested" / "state.json.tmp").exists()
