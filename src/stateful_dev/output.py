import json


def to_json(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n"
