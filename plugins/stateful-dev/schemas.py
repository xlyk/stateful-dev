from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DoctorInput:
    state: str


@dataclass(frozen=True)
class ReportInput:
    state: str
    run_summary: dict[str, Any] = field(default_factory=dict)
