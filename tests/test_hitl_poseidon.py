"""Tests for Poseidon HITL polling integrated into the cron-gate path.

Task 5: Add Poseidon HITL polling to cron-gate preflight path.
These tests cover the optional HITL polling capability without requiring
HITL to be enabled for every worker.
"""
import json
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app


def _write_state_with_hitl(
    path: Path,
    hitl_config: dict | None,
    items: list[dict],
) -> None:
    """Write a state file with an optional HITL block."""
    counts = {s: 0 for s in [
        "pending", "in_progress", "red_verified", "green_verified",
        "succeeded", "needs_review", "blocked", "failed_retryable",
        "failed_final", "skipped",
    ]}
    for item in items:
        counts[item["status"]] += 1

    state = {
        "job_name": "test-hitl-worker",
        "version": 1,
        "project_root": str(path.parent),
        "plan_paths": ["docs/plans/test.md"],
        "state_path": str(path),
        "counts": counts,
        "items": items,
    }
    if hitl_config is not None:
        state["hitl"] = hitl_config

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def _doctor(state_path: Path) -> tuple[int, dict]:
    result = CliRunner().invoke(
        app, ["doctor", "--state", str(state_path), "--json"]
    )
    return result.exit_code, json.loads(result.output)


def _claim(state_path: Path, run_id: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["claim", "--state", str(state_path), "--run-id", run_id]
    )
    return result.exit_code, result.output


class TestHITLStateSchemaValidation:
    """doctor validates HITL block shape when present."""

    def test_doctor_accepts_state_without_hitl_block(self, tmp_path: Path) -> None:
        """Non-HITL workers are unaffected — no hitl block is fine."""
        state_path = tmp_path / "state.json"
        _write_state_with_hitl(
            state_path,
            hitl_config=None,
            items=[{"id": "plan:T1", "title": "One", "status": "pending"}],
        )
        exit_code, payload = _doctor(state_path)
        assert exit_code == 0
        assert payload["ok"] is True, payload.get("errors")

    def test_doctor_accepts_valid_hitl_block(self, tmp_path: Path) -> None:
        """A correctly shaped HITL block passes validation."""
        state_path = tmp_path / "state.json"
        hitl = {
            "enabled": True,
            "provider": "poseidon",
            "node_id": "test-node",
            "worker_id": "test-worker",
            "state_path_hash": "sha256:abc123",
            "poll_policy": "required",
            "active_requests": [],
        }
        _write_state_with_hitl(
            state_path,
            hitl_config=hitl,
            items=[{"id": "plan:T1", "title": "One", "status": "pending"}],
        )
        exit_code, payload = _doctor(state_path)
        assert exit_code == 0
        assert payload["ok"] is True, payload.get("errors")

    def test_doctor_rejects_hitl_enabled_without_provider(
        self, tmp_path: Path
    ) -> None:
        """HITL enabled requires provider field."""
        state_path = tmp_path / "state.json"
        hitl = {
            "enabled": True,
            "node_id": "test-node",
            "worker_id": "test-worker",
            "state_path_hash": "sha256:abc123",
            "poll_policy": "required",
            "active_requests": [],
        }
        _write_state_with_hitl(
            state_path,
            hitl_config=hitl,
            items=[{"id": "plan:T1", "title": "One", "status": "pending"}],
        )
        exit_code, payload = _doctor(state_path)
        assert exit_code == 1
        assert payload["ok"] is False
        errors = " ".join(payload.get("errors", [])).lower()
        assert "provider" in errors

    def test_doctor_rejects_invalid_poll_policy(self, tmp_path: Path) -> None:
        """poll_policy must be 'required' or 'optional'."""
        state_path = tmp_path / "state.json"
        hitl = {
            "enabled": True,
            "provider": "poseidon",
            "node_id": "test-node",
            "worker_id": "test-worker",
            "state_path_hash": "sha256:abc123",
            "poll_policy": "invalid-policy",
            "active_requests": [],
        }
        _write_state_with_hitl(
            state_path,
            hitl_config=hitl,
            items=[{"id": "plan:T1", "title": "One", "status": "pending"}],
        )
        exit_code, payload = _doctor(state_path)
        assert exit_code == 1
        assert payload["ok"] is False


class TestClaimHITLIntegration:
    """claim respects HITL poll-before-run enforcement when HITL is enabled."""

    def test_claim_succeeds_when_hitl_not_enabled(self, tmp_path: Path) -> None:
        """When no HITL block, claim proceeds normally."""
        state_path = tmp_path / "state.json"
        _write_state_with_hitl(
            state_path,
            hitl_config=None,
            items=[{
                "id": "plan:T1",
                "title": "One",
                "status": "pending",
                "attempts": 0,
            }],
        )
        exit_code, output = _claim(state_path, "run-1")
        assert exit_code == 0
        payload = json.loads(output)
        assert payload["claimed"] is True
        assert payload["item"]["id"] == "plan:T1"

    def test_claim_refuses_when_hitl_enabled_but_no_poll_marker(
        self, tmp_path: Path
    ) -> None:
        """When HITL is enabled and no run-level poll marker exists, claim refuses."""
        state_path = tmp_path / "state.json"
        hitl = {
            "enabled": True,
            "provider": "poseidon",
            "node_id": "test-node",
            "worker_id": "test-worker",
            "state_path_hash": "sha256:abc123",
            "poll_policy": "required",
            "active_requests": [],
        }
        _write_state_with_hitl(
            state_path,
            hitl_config=hitl,
            items=[{
                "id": "plan:T1",
                "title": "One",
                "status": "pending",
                "attempts": 0,
            }],
        )
        exit_code, output = _claim(state_path, "run-1")
        # Should exit non-zero because HITL poll is required but no marker exists
        assert exit_code == 1
        assert "hitl" in output.lower() or "poll" in output.lower()

    def test_claim_refuses_when_hitl_poll_failed(self, tmp_path: Path) -> None:
        """When HITL poll failed and policy is required, claim refuses."""
        state_path = tmp_path / "state.json"
        hitl = {
            "enabled": True,
            "provider": "poseidon",
            "node_id": "test-node",
            "worker_id": "test-worker",
            "state_path_hash": "sha256:abc123",
            "poll_policy": "required",
            "active_requests": [],
            "last_poll": {
                "run_id": "run-1",
                "ok": False,
                "error": "connection refused",
            },
        }
        _write_state_with_hitl(
            state_path,
            hitl_config=hitl,
            items=[{
                "id": "plan:T1",
                "title": "One",
                "status": "pending",
                "attempts": 0,
            }],
        )
        exit_code, output = _claim(state_path, "run-2")
        assert exit_code == 1
        assert "hitl" in output.lower() or "poll" in output.lower()

    def test_claim_proceeds_hitl_enabled_with_successful_poll_marker(
        self, tmp_path: Path
    ) -> None:
        """HITL enabled + successful poll marker -> claim proceeds."""
        state_path = tmp_path / "state.json"
        hitl = {
            "enabled": True,
            "provider": "poseidon",
            "node_id": "test-node",
            "worker_id": "test-worker",
            "state_path_hash": "sha256:abc123",
            "poll_policy": "required",
            "active_requests": [],
        }
        _write_state_with_hitl(
            state_path,
            hitl_config=hitl,
            items=[{
                "id": "plan:T1",
                "title": "One",
                "status": "pending",
                "attempts": 0,
            }],
        )
        # Simulate a successful poll by writing a run marker
        runs_dir = state_path.parent / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        run_marker = runs_dir / "run-1.json"
        run_marker.write_text(json.dumps({
            "run_id": "run-1",
            "hitl_poll": {
                "required": True,
                "ok": True,
                "completed_at": "2026-04-27T10:00:00Z",
                "worker_id": "test-worker",
                "request_ids": [],
            },
        }), encoding="utf-8")

        exit_code, output = _claim(state_path, "run-1")
        assert exit_code == 0
        payload = json.loads(output)
        assert payload["claimed"] is True
        assert payload["item"]["id"] == "plan:T1"

    def test_claim_refuses_when_poll_marker_run_id_mismatches(
        self, tmp_path: Path
    ) -> None:
        """The run marker's embedded run_id must match the claimed run."""
        state_path = tmp_path / "state.json"
        hitl = {
            "enabled": True,
            "provider": "poseidon",
            "node_id": "test-node",
            "worker_id": "test-worker",
            "state_path_hash": "sha256:abc123",
            "poll_policy": "required",
            "active_requests": [],
        }
        _write_state_with_hitl(
            state_path,
            hitl_config=hitl,
            items=[{
                "id": "plan:T1",
                "title": "One",
                "status": "pending",
                "attempts": 0,
            }],
        )
        runs_dir = state_path.parent / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / "run-1.json").write_text(json.dumps({
            "run_id": "different-run",
            "hitl_poll": {
                "required": True,
                "ok": True,
                "completed_at": "2026-04-27T10:00:00Z",
                "worker_id": "test-worker",
                "request_ids": [],
            },
        }), encoding="utf-8")

        exit_code, output = _claim(state_path, "run-1")
        assert exit_code == 1
        assert "run_id" in output or "mismatch" in output.lower()


class TestHITLPollCommandExists:
    """The hitl poll-before-run command exists and accepts required arguments."""

    def test_hitl_poll_command_exists(self) -> None:
        """stateful-dev hitl --help should list poll-before-run subcommand."""
        result = CliRunner().invoke(app, ["hitl", "--help"])
        # Command may not exist yet — this is the RED
        assert result.exit_code == 0
        assert "poll" in result.output.lower()


class TestPoseidonPollingModule:
    """The hitl_poseidon module provides injectable Poseidon polling."""

    def test_hitl_poseidon_module_exists(self) -> None:
        """src/stateful_dev/hitl_poseidon.py must exist."""
        import stateful_dev.hitl_poseidon as hp

        assert hasattr(hp, "poll_poseidon")
        assert hasattr(hp, "validate_event")
        assert hasattr(hp, "compute_state_path_hash")
        assert hasattr(hp, "hitl_enabled")
        assert hasattr(hp, "hitl_poll_ok_for_run")
