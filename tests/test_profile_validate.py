"""Tests for the profile validate command — deployment_profile.json validation.

RED: command does not exist (exit 2, no such subcommand).
GREEN: command exists and validates all required deployment profile fields.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app

runner = CliRunner()


def _write_profile(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class TestProfileValidateCommandExists:
    """Verify the profile validate command exists and is reachable."""

    def test_profile_subcommand_exists(self) -> None:
        """RED: exit 2 — profile command does not exist."""
        result = runner.invoke(app, ["profile", "--help"])
        msg = f"Expected profile command to exist, got: {result.output}"
        assert result.exit_code != 2, msg

    def test_profile_validate_subcommand_exists(self) -> None:
        """RED: exit 2 — profile validate command does not exist."""
        result = runner.invoke(app, ["profile", "validate", "--help"])
        msg = f"Expected profile validate to exist, got: {result.output}"
        assert result.exit_code != 2, msg


class TestProfileValidateValidProfile:
    """Verify profile validate accepts a complete valid deployment profile."""

    def test_validate_succeeds_for_complete_valid_profile(
        self, tmp_path: Path
    ) -> None:
        """GREEN: validates a complete, well-formed deployment profile."""
        profile_path = tmp_path / "deployment_profile.json"
        valid_profile = {
            "version": 1,
            "project_root": str(tmp_path / "project"),
            "plan_paths": [str(tmp_path / "plan.md")],
            "state_path": str(tmp_path / "state.json"),
            "gates": {
                "require_full_suite": True,
                "require_lint": True,
            },
            "todoist": {
                "project_id": "6gV7Qgm6PWwrHhM2",
                "sync_on_transition": False,
            },
            "notification_policy": {
                "on_blocker": "notify",
                "on_complete": "notify",
            },
            "script_wrapper": {
                "enabled": True,
                "wrapper_name": (
                    "stateful_dev_stateful-dev-cron-gate-worker_gate.py"
                ),
            },
            "cron_permissions": {
                "allowed_schedule_hours": list(range(24)),
                "max_items_per_run": 1,
            },
            "secret_files": [],
        }
        # Create the project_root so the validation path-check passes
        (tmp_path / "project").mkdir()
        (tmp_path / "plan.md").write_text("# plan")
        _write_profile(profile_path, valid_profile)
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", str(profile_path), "--json"],
        )
        assert result.exit_code == 0, f"Expected valid profile to pass: {result.output}"
        payload = json.loads(result.stdout)
        assert payload.get("valid") is True
        assert payload.get("errors") == []


class TestProfileValidateRequiredFields:
    """Verify profile validate detects missing or invalid required fields."""

    def test_missing_project_root(self, tmp_path: Path) -> None:
        """RED: missing project_root must be reported as error."""
        profile_path = tmp_path / "deployment_profile.json"
        _write_profile(profile_path, {"version": 1})
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", str(profile_path), "--json"],
        )
        assert result.exit_code == 1, f"Expected validation failure: {result.output}"
        payload = json.loads(result.stdout)
        assert payload.get("valid") is False
        errors = payload.get("errors", [])
        assert any("project_root" in str(e).lower() for e in errors)

    def test_missing_plan_paths(self, tmp_path: Path) -> None:
        """RED: missing plan_paths must be reported as error."""
        profile_path = tmp_path / "deployment_profile.json"
        _write_profile(profile_path, {
            "version": 1,
            "project_root": str(tmp_path),
        })
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", str(profile_path), "--json"],
        )
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload.get("valid") is False
        errors = payload.get("errors", [])
        assert any("plan_paths" in str(e).lower() for e in errors)

    def test_missing_state_path(self, tmp_path: Path) -> None:
        """RED: missing state_path must be reported as error."""
        profile_path = tmp_path / "deployment_profile.json"
        _write_profile(profile_path, {
            "version": 1,
            "project_root": str(tmp_path),
            "plan_paths": [str(tmp_path / "plan.md")],
        })
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", str(profile_path), "--json"],
        )
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload.get("valid") is False
        errors = payload.get("errors", [])
        assert any("state_path" in str(e).lower() for e in errors)

    def test_invalid_project_root_path(self, tmp_path: Path) -> None:
        """RED: project_root that does not exist must be reported as error."""
        profile_path = tmp_path / "deployment_profile.json"
        _write_profile(profile_path, {
            "version": 1,
            "project_root": str(tmp_path / "nonexistent"),
            "plan_paths": [str(tmp_path / "plan.md")],
            "state_path": str(tmp_path / "state.json"),
        })
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", str(profile_path), "--json"],
        )
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload.get("valid") is False
        errors = payload.get("errors", [])
        assert any("project_root" in str(e).lower() for e in errors)

    def test_missing_gates(self, tmp_path: Path) -> None:
        """RED: missing gates section must be reported as error."""
        profile_path = tmp_path / "deployment_profile.json"
        _write_profile(profile_path, {
            "version": 1,
            "project_root": str(tmp_path),
            "plan_paths": [str(tmp_path / "plan.md")],
            "state_path": str(tmp_path / "state.json"),
        })
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", str(profile_path), "--json"],
        )
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload.get("valid") is False
        errors = payload.get("errors", [])
        assert any("gates" in str(e).lower() for e in errors)

    def test_missing_todoist_mapping(self, tmp_path: Path) -> None:
        """RED: missing todoist mapping must be reported as error."""
        profile_path = tmp_path / "deployment_profile.json"
        _write_profile(profile_path, {
            "version": 1,
            "project_root": str(tmp_path),
            "plan_paths": [str(tmp_path / "plan.md")],
            "state_path": str(tmp_path / "state.json"),
            "gates": {"require_full_suite": True, "require_lint": True},
        })
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", str(profile_path), "--json"],
        )
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload.get("valid") is False
        errors = payload.get("errors", [])
        assert any("todoist" in str(e).lower() for e in errors)

    def test_missing_notification_policy(self, tmp_path: Path) -> None:
        """RED: missing notification_policy must be reported as error."""
        profile_path = tmp_path / "deployment_profile.json"
        _write_profile(profile_path, {
            "version": 1,
            "project_root": str(tmp_path),
            "plan_paths": [str(tmp_path / "plan.md")],
            "state_path": str(tmp_path / "state.json"),
            "gates": {"require_full_suite": True, "require_lint": True},
            "todoist": {"project_id": "abc123", "sync_on_transition": False},
        })
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", str(profile_path), "--json"],
        )
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload.get("valid") is False
        errors = payload.get("errors", [])
        assert any("notification_policy" in str(e).lower() for e in errors)


class TestProfileValidateNonexistentFile:
    """Verify profile validate handles nonexistent files gracefully."""

    def test_validate_nonexistent_file(self) -> None:
        """RED: nonexistent profile file must be reported as error."""
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", "/nonexistent/profile.json", "--json"],
        )
        assert result.exit_code == 2
        payload = json.loads(result.stdout)
        assert payload.get("valid") is False
        assert "not found" in str(payload.get("errors", [])).lower()


class TestProfileValidateWarnings:
    """Verify profile validate produces warnings for optional-but-recommended fields."""

    def test_warns_on_missing_script_wrapper(self, tmp_path: Path) -> None:
        """WARN: missing script_wrapper config should produce a warning, not error."""
        profile_path = tmp_path / "deployment_profile.json"
        _write_profile(profile_path, {
            "version": 1,
            "project_root": str(tmp_path),
            "plan_paths": [str(tmp_path / "plan.md")],
            "state_path": str(tmp_path / "state.json"),
            "gates": {"require_full_suite": True, "require_lint": True},
            "todoist": {"project_id": "abc123", "sync_on_transition": False},
            "notification_policy": {"on_blocker": "notify", "on_complete": "silent"},
            "cron_permissions": {
                "allowed_schedule_hours": [9, 10, 11],
                "max_items_per_run": 1,
            },
            "secret_files": [],
        })
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", str(profile_path), "--json"],
        )
        assert result.exit_code == 0, f"script_wrapper is optional: {result.output}"
        payload = json.loads(result.stdout)
        assert payload.get("valid") is True
        warnings = payload.get("warnings", [])
        assert any("script_wrapper" in str(w).lower() for w in warnings)

    def test_warns_on_missing_cron_permissions(self, tmp_path: Path) -> None:
        """WARN: missing cron_permissions should produce a warning, not error."""
        profile_path = tmp_path / "deployment_profile.json"
        _write_profile(profile_path, {
            "version": 1,
            "project_root": str(tmp_path),
            "plan_paths": [str(tmp_path / "plan.md")],
            "state_path": str(tmp_path / "state.json"),
            "gates": {"require_full_suite": True, "require_lint": True},
            "todoist": {"project_id": "abc123", "sync_on_transition": False},
            "notification_policy": {"on_blocker": "notify", "on_complete": "silent"},
            "script_wrapper": {"enabled": False},
            "secret_files": [],
        })
        result = runner.invoke(
            app,
            ["profile", "validate", "--profile", str(profile_path), "--json"],
        )
        assert result.exit_code == 0, f"cron_permissions is optional: {result.output}"
        payload = json.loads(result.stdout)
        assert payload.get("valid") is True
        warnings = payload.get("warnings", [])
        assert any("cron_permissions" in str(w).lower() for w in warnings)


class TestProfileRenderValidation:
    def test_render_reuses_full_profile_validation(self, tmp_path: Path) -> None:
        """Render must reject profiles missing validate-required fields."""
        profile_path = tmp_path / "deployment_profile.json"
        _write_profile(profile_path, {
            "version": 1,
            "project_root": str(tmp_path),
            "executor_prompt_template": "Work on {item_id}: {item_title}",
        })

        result = runner.invoke(
            app,
            [
                "profile",
                "render",
                "--profile",
                str(profile_path),
                "--item-id",
                "sample:T1",
                "--item-title",
                "Sample task",
                "--item-status",
                "pending",
                "--json",
            ],
        )

        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["valid"] is False
        assert any("plan_paths" in error for error in payload["errors"])
        assert any("gates" in error for error in payload["errors"])
