import json

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


def test_write_json_atomic_uses_unique_sibling_temp_file_and_replace(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "state.json"
    calls = []
    original_replace = type(target).replace

    def spy_replace(self, target_path):
        calls.append((self, target_path))
        return original_replace(self, target_path)

    monkeypatch.setattr(type(target), "replace", spy_replace)

    write_json_atomic(target, {"ok": True})

    assert target.read_text(encoding="utf-8") == '{\n  "ok": true\n}\n'
    assert len(calls) == 1
    temp_path, replaced_target = calls[0]
    assert temp_path.parent == target.parent
    assert temp_path.name.startswith("state.json.")
    assert temp_path.name.endswith(".tmp")
    assert replaced_target == target
    assert not temp_path.exists()


def test_write_json_atomic_does_not_clobber_existing_fixed_tmp_file(tmp_path):
    target = tmp_path / "state.json"
    sentinel = tmp_path / "state.json.tmp"
    sentinel.write_text("sentinel", encoding="utf-8")

    write_json_atomic(target, {"ok": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}
    assert sentinel.read_text(encoding="utf-8") == "sentinel"
