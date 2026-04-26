import json
from pathlib import Path
from typing import Annotated

import typer

from stateful_dev import __version__
from stateful_dev.output import to_json
from stateful_dev.state import validate_state

app = typer.Typer(help="Stateful development worker utilities.")


@app.callback()
def main() -> None:
    """Stateful development worker utilities."""


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def doctor(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Validate a durable worker state file."""
    data = json.loads(state.read_text(encoding="utf-8"))
    result = validate_state(data)
    payload = {
        "ok": result.ok,
        "errors": result.errors,
        "warnings": result.warnings,
        "counts": result.counts,
    }
    if as_json:
        typer.echo(to_json(payload), nl=False)
    else:
        typer.echo("ok" if result.ok else "invalid")
    if not result.ok:
        raise typer.Exit(1)
