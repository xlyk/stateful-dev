import typer

app = typer.Typer(help="Stateful development worker utilities.")


@app.callback()
def main() -> None:
    """Stateful development worker utilities."""
