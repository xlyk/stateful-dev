"""Render worker prompts from validated deployment profiles."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app

runner = CliRunner()


def _write_profile(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class TestProfileRenderCommandExists:
    """Verify the profile render command exists and is reachable."""

    def test_render_subcommand_exists(self) -> None:
        """RED: exit 2 — profile render command does not exist."""
        result = runner.invoke(app, ["profile", "render", "--help"])
        msg = f"Expected profile render to exist, got: {result.output}"
        assert result.exit_code != 2, msg


class TestProfileRenderRequiresValidProfile:
    """Verify profile render validates the profile before rendering."""

    def test_render_fails_if_profile_does_not_exist(self, tmp_path: Path) -> None:
        """RED: nonexistent profile must cause exit 2."""
        result = runner.invoke(
            app,
            [
                "profile",
                "render",
                "--profile",
                str(tmp_path / "nonexistent.json"),
                "--item-id",
                "test-item",
                "--item-title",
                "Test Item",
                "--item-status",
                "in_progress",
            ],
        )
        expected = "Expected exit 2 for missing profile"
        assert result.exit_code == 2, f"{expected}: {result.output}"

    def test_render_fails_if_profile_is_invalid(self, tmp_path: Path) -> None:
        """RED: invalid profile must cause exit 1."""
        profile_path = tmp_path / "deployment_profile.json"
        _write_profile(profile_path, {"version": 1})  # missing required fields
        result = runner.invoke(
            app,
            [
                "profile",
                "render",
                "--profile",
                str(profile_path),
                "--item-id",
                "test-item",
                "--item-title",
                "Test Item",
                "--item-status",
                "in_progress",
            ],
        )
        expected = "Expected exit 1 for invalid profile"
        assert result.exit_code == 1, f"{expected}: {result.output}"

    def test_render_succeeds_if_profile_is_valid(self, tmp_path: Path) -> None:
        """GREEN: valid profile with executor_prompt_template allows render."""
        profile_path = tmp_path / "deployment_profile.json"
        template = (
            "Item: {item_id}\\nTitle: {item_title}\\n"
            "Status: {item_status}\\nProcess the item."
        )
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
            "executor_prompt_template": template,
        }
        (tmp_path / "project").mkdir()
        (tmp_path / "plan.md").write_text("# plan")
        _write_profile(profile_path, valid_profile)
        result = runner.invoke(
            app,
            [
                "profile",
                "render",
                "--profile",
                str(profile_path),
                "--item-id",
                "test-item-1",
                "--item-title",
                "My Test Item",
                "--item-status",
                "in_progress",
            ],
        )
        expected = "Expected exit 0 for valid profile"
        assert result.exit_code == 0, f"{expected}: {result.output}"
        # Output should contain rendered content with item info substituted
        assert "test-item-1" in result.output
        assert "My Test Item" in result.output
        assert "in_progress" in result.output


class TestProfileRenderMissingTemplate:
    """Verify render fails when executor_prompt_template is absent."""

    def test_render_fails_without_executor_prompt_template(
        self, tmp_path: Path
    ) -> None:
        """RED: valid profile but missing executor_prompt_template causes exit 1."""
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
            # intentionally no executor_prompt_template
        }
        (tmp_path / "project").mkdir()
        (tmp_path / "plan.md").write_text("# plan")
        _write_profile(profile_path, valid_profile)
        result = runner.invoke(
            app,
            [
                "profile",
                "render",
                "--profile",
                str(profile_path),
                "--item-id",
                "test-item",
                "--item-title",
                "Test Item",
                "--item-status",
                "in_progress",
            ],
        )
        expected = "Expected exit 1 without template"
        assert result.exit_code == 1, f"{expected}: {result.output}"
        # plain text output mentions the missing field
        assert "executor_prompt_template" in result.output


class TestProfileRenderJsonOutput:
    """Verify profile render emits structured JSON when --json is used."""

    def test_render_json_output_shape(self, tmp_path: Path) -> None:
        """GREEN: --json output includes rendered_prompt, profile_path, item context."""
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
            "executor_prompt_template": "Work on {item_id}: {item_title}.",
        }
        (tmp_path / "project").mkdir()
        (tmp_path / "plan.md").write_text("# plan")
        _write_profile(profile_path, valid_profile)
        result = runner.invoke(
            app,
            [
                "profile",
                "render",
                "--profile",
                str(profile_path),
                "--item-id",
                "item-99",
                "--item-title",
                "Final Item",
                "--item-status",
                "in_progress",
                "--json",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "rendered_prompt" in payload
        assert "item_id" in payload
        assert "item_title" in payload
        assert "item_status" in payload
        assert "profile_path" in payload
        assert payload["rendered_prompt"] == "Work on item-99: Final Item."
        assert payload["item_id"] == "item-99"
        assert payload["item_title"] == "Final Item"
        assert payload["item_status"] == "in_progress"
