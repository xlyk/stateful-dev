import re
from dataclasses import dataclass
from pathlib import Path

_TASK_HEADING = re.compile(r"^## Task (?P<number>\d+): (?P<title>.+)$")


@dataclass(frozen=True)
class PlanTask:
    plan_path: Path
    number: int
    heading: str
    title: str
    body: str


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
                tasks.append(
                    PlanTask(
                        plan_path=path,
                        number=int(current["number"]),
                        heading=str(current["heading"]),
                        title=str(current["title"]),
                        body="\n".join(body_lines).strip(),
                    )
                )
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
        tasks.append(
            PlanTask(
                plan_path=path,
                number=int(current["number"]),
                heading=str(current["heading"]),
                title=str(current["title"]),
                body="\n".join(body_lines).strip(),
            )
        )

    return tasks
