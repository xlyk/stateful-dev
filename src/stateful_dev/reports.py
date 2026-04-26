from collections.abc import Iterable, Mapping
from typing import Any


def _count(state: Mapping[str, Any], status: str) -> int:
    counts = state.get("counts", {})
    if not isinstance(counts, Mapping):
        return 0
    value = counts.get(status, 0)
    return value if isinstance(value, int) else 0


def _remaining_count(state: Mapping[str, Any]) -> int:
    return sum(
        _count(state, status)
        for status in (
            "pending",
            "in_progress",
            "red_verified",
            "green_verified",
            "failed_retryable",
        )
    )


def _processed_items(run_summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    processed = run_summary.get("processed", [])
    if not isinstance(processed, list):
        return []
    return [item for item in processed if isinstance(item, Mapping)]


def _status_total(items: Iterable[Mapping[str, Any]], status: str) -> int:
    return sum(1 for item in items if item.get("status") == status)


def _item_line(item: Mapping[str, Any]) -> str:
    item_id = item.get("id", "unknown")
    title = item.get("title", "untitled")
    commit_sha = item.get("commit_sha") or "no commit"
    return f"- {item_id}: {title} ({commit_sha})"


def _gate_lines(run_summary: Mapping[str, Any]) -> list[str]:
    gates = run_summary.get("gates", {})
    if not isinstance(gates, Mapping):
        gates = {}
    return [
        "Gates:",
        f"- focused: {gates.get('focused', 'not run')}",
        f"- full suite: {gates.get('full suite', 'not run')}",
        f"- lint: {gates.get('lint', 'not run')}",
    ]


def _todoist_lines(run_summary: Mapping[str, Any]) -> list[str]:
    todoist = run_summary.get("todoist", {})
    if not isinstance(todoist, Mapping):
        todoist = {}
    return [
        "Todoist:",
        f"- project: {todoist.get('project', 'not configured')}",
        f"- task: {todoist.get('task', 'not configured')}",
    ]


def render_batch_report(
    state: Mapping[str, Any], run_summary: Mapping[str, Any]
) -> str:
    processed = _processed_items(run_summary)
    failed = _status_total(processed, "failed_retryable") + _status_total(
        processed, "failed_final"
    )
    needs_review = _status_total(processed, "needs_review")
    lines = [
        f"{state.get('job_name', 'stateful-dev-worker')} development batch",
        "",
        f"Plan: {run_summary.get('plan', 'unknown')}",
        f"Processed: {len(processed)}",
        f"Succeeded: {_status_total(processed, 'succeeded')}",
        f"Failed: {failed}",
        f"Needs review: {needs_review}",
        f"Remaining: {_remaining_count(state)}",
        "",
    ]

    completed = [item for item in processed if item.get("status") == "succeeded"]
    if completed:
        lines.append("Completed:")
        lines.extend(_item_line(item) for item in completed)
        lines.append("")

    review_items = [item for item in processed if item.get("status") == "needs_review"]
    if review_items:
        lines.append("Needs review:")
        lines.extend(_item_line(item) for item in review_items)
        lines.append("")

    failed_items = [
        item
        for item in processed
        if item.get("status") in {"failed_retryable", "failed_final"}
    ]
    if failed_items:
        lines.append("Failures:")
        lines.extend(_item_line(item) for item in failed_items)
        lines.append("")

    lines.extend(_gate_lines(run_summary))
    lines.append("")
    lines.extend(_todoist_lines(run_summary))
    lines.append("")
    lines.append(f"State: {run_summary.get('state_path', 'unknown')}")
    lines.append(f"Next: {run_summary.get('next_action', 'unknown')}")
    return "\n".join(lines) + "\n"


def render_operator_handoff(
    *,
    job_name: str,
    question: str,
    why: str,
    recommended_answer: str,
    project_root: str,
    plan_path: str,
    state_path: str,
    item_id: str,
    title: str,
    status: str,
    evidence: list[str],
    allowed_next_action: str,
) -> str:
    evidence_lines = [f"- {line}" for line in evidence]
    return "\n".join(
        [
            f"{job_name} needs operator input",
            "",
            f"Question: {question}",
            f"Why it matters: {why}",
            f"Recommended answer: {recommended_answer}",
            "",
            "Context:",
            f"- Project: {project_root}",
            f"- Plan: {plan_path}",
            f"- State: {state_path}",
            f"- Item: {item_id} — {title}",
            f"- Status: {status}",
            f"- Evidence: {'; '.join(evidence)}",
            "",
            "Fresh agent handoff — copy/paste:",
            "---",
            "You are continuing a stateful TDD development worker.",
            f"Project root: {project_root}",
            f"Plan file: {plan_path}",
            f"State file: {state_path}",
            f"Current item: {item_id} — {title}",
            f"Current status: {status}",
            f"Blocking question: {question}",
            "Relevant evidence:",
            *evidence_lines,
            f"Allowed next action: {allowed_next_action}",
            "Do not push. Do not bypass RED/GREEN verification. "
            "Use existing state and update it before exiting.",
            "---",
            "",
        ]
    )
