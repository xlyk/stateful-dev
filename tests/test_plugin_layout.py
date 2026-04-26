import importlib.util
from pathlib import Path


def load_plugin_tools():
    tools_path = Path("plugins/stateful-dev/tools.py")
    spec = importlib.util.spec_from_file_location(
        "stateful_dev_plugin_tools", tools_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecordingContext:
    def __init__(self):
        self.tools = []

    def tool(self, name, handler, schema=None, description=None):
        self.tools.append(
            {
                "name": name,
                "handler": handler,
                "schema": schema,
                "description": description,
            }
        )


def test_plugin_exposes_register_function():
    plugin_yaml = Path("plugins/stateful-dev/plugin.yaml")
    assert plugin_yaml.exists()
    assert "stateful-dev" in plugin_yaml.read_text(encoding="utf-8")

    tools = load_plugin_tools()
    assert callable(tools.register)

    ctx = RecordingContext()
    tools.register(ctx)

    registered = {tool["name"]: tool for tool in ctx.tools}
    assert "stateful_dev_doctor" in registered
    assert callable(registered["stateful_dev_doctor"]["handler"])
