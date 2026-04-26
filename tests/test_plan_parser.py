from pathlib import Path

from stateful_dev.plan_parser import parse_plan_tasks


def test_parse_task_headings_with_bodies(tmp_path: Path):
    plan_path = tmp_path / "2026-04-26_095545-stateful-dev-02-plan-and-state.md"
    plan_path.write_text(
        "# Milestone\n\n"
        "Intro text that should not become a task.\n\n"
        "## Task 1: Parse task headings from a plan file\n\n"
        "**Objective:** Extract task blocks.\n\n"
        "**RED command:** `pytest one`\n\n"
        "## Notes\n\n"
        "Nested note text stays in the first task body.\n\n"
        "## Task 2: Generate stable item IDs\n\n"
        "**Objective:** Generate IDs.\n",
        encoding="utf-8",
    )

    tasks = parse_plan_tasks(plan_path)

    assert len(tasks) == 2
    assert tasks[0].plan_path == plan_path
    assert tasks[0].number == 1
    assert tasks[0].heading == "## Task 1: Parse task headings from a plan file"
    assert tasks[0].title == "Parse task headings from a plan file"
    assert "**Objective:** Extract task blocks." in tasks[0].body
    assert "Nested note text stays in the first task body." in tasks[0].body
    assert "## Task 2" not in tasks[0].body
    assert tasks[1].number == 2
    assert tasks[1].title == "Generate stable item IDs"
    assert "**Objective:** Generate IDs." in tasks[1].body


def test_item_ids_are_stable_slugs(tmp_path: Path):
    plan_path = tmp_path / "2026-04-26_095545-stateful-dev-02-plan-and-state.md"
    plan_path.write_text(
        "## Task 2: Generate stable item IDs!\n\n"
        "Body one.\n\n"
        "## Task 10: Validate state schema & counts\n\n"
        "Body two.\n",
        encoding="utf-8",
    )

    first_parse = parse_plan_tasks(plan_path)
    second_parse = parse_plan_tasks(plan_path)

    assert [task.item_id for task in first_parse] == [
        "2026-04-26-095545-stateful-dev-02-plan-and-state:T2-generate-stable-item-ids",
        "2026-04-26-095545-stateful-dev-02-plan-and-state:T10-validate-state-schema-counts",
    ]
    assert [task.item_id for task in second_parse] == [
        task.item_id for task in first_parse
    ]
