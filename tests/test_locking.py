import pytest

from stateful_dev.locking import FreshLockError, acquire_lock, release_lock


def test_acquire_lock_refuses_fresh_existing_lock(tmp_path):
    lock = acquire_lock(tmp_path, run_id="run-1", timeout_minutes=60)

    try:
        with pytest.raises(FreshLockError, match="run-1"):
            acquire_lock(tmp_path, run_id="run-2", timeout_minutes=60)
    finally:
        release_lock(lock)
