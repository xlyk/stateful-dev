import re
from dataclasses import dataclass
from pathlib import Path

_TASK_HEADING = re.compile(r"^## Task (?P<number>\d+): (?P<title>.+)$")
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class PlanTask:
    plan_path: Path
    number: int
    heading: str
    title: str
    body: str
    item_id: str


def _slug(text: str) -> str:
    return _NON_SLUG_CHARS.sub("-", text.lower()).strip("-")


def _item_id(path: Path, number: int, title: str) -> str:
    return f"{_slug(path.stem)}:T{number}-{_slug(title)}"


def _task_from_current(
    path: Path, current: dict[str, object], body_lines: list[str]
) -> PlanTask:
    number = int(current["number"])
    title = str(current["title"])
    return PlanTask(
        plan_path=path,
        number=number,
        heading=str(current["heading"]),
        title=title,
        body="\n".join(body_lines).strip(),
        item_id=_item_id(path, number, title),
    )


def parse_plan_tasks(path: Path) -> list[PlanTask]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tasks: list[PlanTask] = []
    current: dict[str, object] | None = None
    body_lines: list[str] = []

    for line in lines:
        match = _TASK_HEADING.match(line)
        if match:
            if current is not None:
                tasks.append(_task_from_current(path, current, body_lines))
            current = {
                "number": int(match.group("number")),
                "heading": line,
                "title": match.group("title"),
            }
            body_lines = []
            continue

        if current is not None:
            body_lines.append(line)

    if current is not None:
        tasks.append(_task_from_current(path, current, body_lines))

    return tasks


@dataclass(frozen=True)
class PlanLintResult:
    ok: bool
    errors: list[str]
    warnings: list[str]
    task_count: int


def lint_plan(path: Path) -> PlanLintResult:
    """Lint a plan file and return issues found.

    Checks:
    - Missing task headings (plan with no ## Task N: ... lines)
    - Duplicate generated item IDs
    """
    errors: list[str] = []
    warnings: list[str] = []

    tasks = parse_plan_tasks(path)

    if not tasks:
        errors.append("plan has no task headings (## Task N: ...)")

    # Check for duplicate generated item IDs
    seen_ids: dict[str, int] = {}
    for task in tasks:
        prev = seen_ids.get(task.item_id)
        if prev is not None:
            errors.append(
                f"duplicate generated item ID '{task.item_id}' at tasks "
                f"{prev + 1} and {task.number}"
            )
        else:
            seen_ids[task.item_id] = task.number - 1

    return PlanLintResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        task_count=len(tasks),
    )
