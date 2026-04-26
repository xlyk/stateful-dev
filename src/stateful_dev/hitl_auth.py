from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
from hmac import compare_digest

HASH_PREFIX = "sha256:"
TEST_TOKEN_PREFIX = "test-token:"


def hash_node_token(token: str) -> str:
    return f"{HASH_PREFIX}{sha256(token.encode()).hexdigest()}"


def make_node_token_verifier(
    node_tokens: Mapping[str, str],
) -> Callable[[str | None], str | None]:
    token_records = dict(node_tokens)

    def verify_token(token: str | None) -> str | None:
        if token is None:
            return None
        for node, configured_token in token_records.items():
            if _token_matches(token, configured_token):
                return node
        return None

    return verify_token


def _token_matches(token: str, configured_token: str) -> bool:
    if configured_token.startswith(HASH_PREFIX):
        return compare_digest(hash_node_token(token), configured_token)
    if configured_token.startswith(TEST_TOKEN_PREFIX):
        return compare_digest(token, configured_token.removeprefix(TEST_TOKEN_PREFIX))
    return False
