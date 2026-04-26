from stateful_dev.reports import render_batch_report, render_operator_handoff


def test_batch_report_includes_counts_state_and_next_action():
    state = {
        "job_name": "stateful-dev-worker",
        "counts": {
            "pending": 1,
            "in_progress": 0,
            "red_verified": 0,
            "green_verified": 0,
            "succeeded": 1,
            "failed_retryable": 0,
            "failed_final": 0,
            "needs_review": 0,
            "blocked": 0,
            "skipped": 0,
        },
    }
    run_summary = {
        "plan": "docs/plans/milestone.md",
        "processed": [
            {
                "id": "plan:T1-one",
                "title": "Do one thing",
                "status": "succeeded",
                "commit_sha": "abc1234",
            }
        ],
        "gates": {"focused": "pass", "full suite": "pass", "lint": "pass"},
        "todoist": {"project": "Stateful Dev", "task": "6gV86XgMQ45hCRFR"},
        "state_path": ".agent-state/stateful-dev-worker/state.json",
        "next_action": "will continue",
    }

    report = render_batch_report(state, run_summary)

    assert report.startswith("stateful-dev-worker development batch\n")
    assert "Plan: docs/plans/milestone.md" in report
    assert "Processed: 1" in report
    assert "Succeeded: 1" in report
    assert "Remaining: 1" in report
    assert "- plan:T1-one: Do one thing (abc1234)" in report
    assert "Gates:\n- focused: pass\n- full suite: pass\n- lint: pass" in report
    assert "Todoist:\n- project: Stateful Dev\n- task: 6gV86XgMQ45hCRFR" in report
    assert "State: .agent-state/stateful-dev-worker/state.json" in report
    assert report.rstrip().endswith("Next: will continue")


def test_operator_handoff_includes_copy_paste_context():
    handoff = render_operator_handoff(
        job_name="stateful-dev-worker",
        question="Should this item accept coverage-only evidence?",
        why="The focused test passed immediately.",
        recommended_answer="Mark needs_review and wait.",
        project_root="/Users/xlyk/Code/stateful-dev",
        plan_path="docs/plans/milestone.md",
        state_path=".agent-state/stateful-dev-worker/state.json",
        item_id="plan:T2-two",
        title="Do another thing",
        status="needs_review",
        evidence=["Focused test passed immediately", "No production code was changed"],
        allowed_next_action="Update the state item after the operator answers.",
    )

    assert handoff.startswith("stateful-dev-worker needs operator input\n")
    assert "Question: Should this item accept coverage-only evidence?" in handoff
    assert "Fresh agent handoff — copy/paste:" in handoff
    assert "Project root: /Users/xlyk/Code/stateful-dev" in handoff
    assert "Current item: plan:T2-two — Do another thing" in handoff
    assert (
        "Allowed next action: Update the state item after the operator answers."
        in handoff
    )
