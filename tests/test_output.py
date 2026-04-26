from stateful_dev.output import to_json


def test_json_output_is_sorted_and_newline_terminated():
    payload = {"z": 1, "a": {"b": 2}}

    assert to_json(payload) == '{"a":{"b":2},"z":1}\n'
