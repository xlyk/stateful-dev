"""Validate that stateful-dev skills document script-backed cron gate architecture.

T14 acceptance criteria: Patch stateful-dev-cron and stateful-dev-helper skills
for script-backed wake gates. Skills must document:
- script-backed wake gates and the scheduler/adapter/stateful-dev/agent boundary
- claim/cron-gate command ownership and responsibilities
- ~/.hermes/scripts restrictions (thin adapters only, no wake-decision logic)
- per-worker wrapper scripts and their contract
- wakeAgent semantics from the cron-gate contract

This test validates the hygiene requirement: the skills must document the
script-backed architecture that was implemented in T1-T9 and dogfooded in T6-T9.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = Path.home() / ".hermes" / "skills"

# Skills that must document script-backed cron gate architecture
REQUIRED_SKILLS = [
    "stateful-dev-cron",
    "stateful-dev-helper",
]

# Required concepts that must appear in the skills
REQUIRED_CONCEPTS = {
    "stateful-dev-cron": [
        # Architecture boundary
        ("~/.hermes/scripts", "thin adapter boundary"),
        ("thin adapter", "per-worker wrappers are thin adapters"),
        ("wake-decision", "wake decisions belong to cron-gate"),
        # Commands
        ("cron-gate", "cron-gate owns local wake decisions"),
        ("claim", "claim atomically selects one item"),
        # Wrappers
        ("per-worker", "per-worker wrapper scripts"),
        ("stateful_dev_", "wrapper naming convention"),
        # wakeAgent
        ("wakeAgent", "wakeAgent JSON field"),
        # Restrictions
        ("no wake-decision", "wrappers must not decide wake"),
    ],
    "stateful-dev-helper": [
        # Architecture boundary
        ("~/.hermes/scripts", "scripts directory restrictions"),
        ("thin adapter", "helper vs adapter responsibilities"),
        # Commands that must be documented as design direction
        ("cron-gate", "cron-gate command design"),
        ("claim", "claim / next command design"),
        # Wrapper ownership
        ("per-worker", "per-worker wrapper responsibilities"),
        ("wake-decision", "wake decision ownership"),
    ],
}


def _load_skill_content(skill_name: str) -> str:
    """Load skill SKILL.md content from ~/.hermes/skills/."""
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        # Fallback: try under category prefix
        for category_dir in SKILLS_DIR.iterdir():
            if category_dir.is_dir():
                candidate = category_dir / skill_name / "SKILL.md"
                if candidate.exists():
                    return candidate.read_text()
        raise FileNotFoundError(f"Skill not found: {skill_name}")
    return skill_path.read_text()


def test_stateful_dev_cron_documents_script_backed_gate():
    """stateful-dev-cron skill must document script-backed cron gate architecture."""
    content = _load_skill_content("stateful-dev-cron")
    missing = []

    for concept, _description in REQUIRED_CONCEPTS["stateful-dev-cron"]:
        if concept.lower() not in content.lower():
            missing.append(concept)

    assert missing == [], (
        "stateful-dev-cron skill is missing required script-backed gate documentation. "
        f"Missing concepts: {missing}. "
        "Must document: scripts restrictions, thin adapter pattern, wake-decision "
        "ownership, cron-gate command, claim command, per-worker wrappers, wakeAgent "
        "semantics, and scheduler/adapter/stateful-dev/agent boundary."
    )


def test_stateful_dev_helper_documents_script_backed_gate():
    """stateful-dev-helper skill must document script-backed gate design direction."""
    content = _load_skill_content("stateful-dev-helper")
    missing = []

    for concept, _description in REQUIRED_CONCEPTS["stateful-dev-helper"]:
        if concept.lower() not in content.lower():
            missing.append(concept)

    assert missing == [], (
        "stateful-dev-helper skill is missing script-backed gate documentation. "
        f"Missing concepts: {missing}. "
        "Must document: cron-gate and claim command design direction, scripts "
        "restrictions, thin adapter pattern, per-worker wrapper responsibilities, "
        "and wake-decision ownership boundary."
    )


def test_stateful_dev_cron_documents_wrapper_exit_code_behavior():
    """stateful-dev-cron must document wrapper exit-code pitfall."""
    content = _load_skill_content("stateful-dev-cron")

    # The wrapper must not convert blocker/error exits into silent wakeAgent:false
    required = [
        "exit",  # wrapper exit code behavior
        "wakeAgent",  # must mention the JSON field
    ]
    missing = [term for term in required if term.lower() not in content.lower()]

    assert missing == [], (
        "stateful-dev-cron must document wrapper exit-code behavior. "
        f"Missing: {missing}. "
        "Key pitfall: a thin wrapper that exits 0 with wakeAgent:false converts a "
        "blocker into a silent skip."
    )
