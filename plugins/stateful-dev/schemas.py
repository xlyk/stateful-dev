from dataclasses import dataclass


@dataclass(frozen=True)
class DoctorInput:
    state: str
