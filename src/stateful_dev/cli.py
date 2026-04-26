import typer

from stateful_dev import __version__

app = typer.Typer(help="Stateful development worker utilities.")


@app.callback()
def main() -> None:
    """Stateful development worker utilities."""


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)
