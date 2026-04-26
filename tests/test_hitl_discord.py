from stateful_dev.hitl_discord import render_hitl_request_card
from stateful_dev.hitl_models import HITLRequest


def test_hitl_request_renders_discord_card_payload():
    request = HITLRequest(
        request_id="hitl_123",
        worker="stateful-dev-worker",
        node="mini.lan",
        project="stateful-dev",
        project_root="/Users/xlyk/Code/stateful-dev",
        state_path=(
            "/Users/xlyk/Code/stateful-dev/.agent-state/"
            "stateful-dev-worker/state.json"
        ),
        state_path_hash="sha256:abc123",
        plan_path="docs/plans/poseidon.md",
        item_id="poseidon:T3-discord-card",
        request_type="clarification",
        status="open",
        question="Should the worker accept the RED exception?",
        allowed_actions=["approve_recommendation", "answer", "deny", "defer"],
        constraints=["do not push", "dry-run-only"],
        payload={
            "recommended_answer": "Accept this as a coverage-only item.",
            "risk": "Bypassing RED/GREEN would weaken confidence.",
        },
        fallback_context="Fresh agent handoff with detailed project context",
        created_at="2026-04-26T20:00:00Z",
        expires_at="2026-04-26T21:00:00Z",
    )

    card = render_hitl_request_card(request)

    assert card == {
        "content": "Stateful worker needs operator input: stateful-dev-worker",
        "embeds": [
            {
                "title": "HITL clarification for stateful-dev",
                "description": "Should the worker accept the RED exception?",
                "color": 15158332,
                "fields": [
                    {"name": "Worker", "value": "stateful-dev-worker", "inline": True},
                    {"name": "Project", "value": "stateful-dev", "inline": True},
                    {
                        "name": "Item",
                        "value": "poseidon:T3-discord-card",
                        "inline": False,
                    },
                    {
                        "name": "Recommendation",
                        "value": "Accept this as a coverage-only item.",
                        "inline": False,
                    },
                    {
                        "name": "Risk / constraints",
                        "value": (
                            "Bypassing RED/GREEN would weaken confidence.\n"
                            "do not push\ndry-run-only"
                        ),
                        "inline": False,
                    },
                    {
                        "name": "State",
                        "value": (
                            "/Users/xlyk/Code/stateful-dev/.agent-state/"
                            "stateful-dev-worker/state.json"
                        ),
                        "inline": False,
                    },
                ],
                "footer": {
                    "text": "Fallback handoff available for request hitl_123"
                },
            }
        ],
        "components": [
            {
                "type": "action_row",
                "components": [
                    {
                        "type": "button",
                        "custom_id": "hitl:hitl_123:approve_recommendation",
                        "label": "Use recommendation",
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "custom_id": "hitl:hitl_123:answer",
                        "label": "Answer",
                        "style": "secondary",
                    },
                    {
                        "type": "button",
                        "custom_id": "hitl:hitl_123:deny",
                        "label": "Deny",
                        "style": "danger",
                    },
                    {
                        "type": "button",
                        "custom_id": "hitl:hitl_123:defer",
                        "label": "Defer",
                        "style": "secondary",
                    },
                ],
            }
        ],
        "metadata": {
            "request_id": "hitl_123",
            "worker": "stateful-dev-worker",
            "node": "mini.lan",
            "item_id": "poseidon:T3-discord-card",
            "state_path_hash": "sha256:abc123",
            "allowed_actions": ["approve_recommendation", "answer", "deny", "defer"],
            "fallback_available": True,
        },
    }
