"""CLI entry point. Every pipeline stage gets its own command here as it's
built (Phase 2+: ingest-paper, clean-paper, extract-questions, ...) so each
stage is runnable and inspectable independently, per PIPELINE.md.
"""

import typer

app = typer.Typer(help="AI Practice Paper Generator CLI")


@app.callback()
def main() -> None:
    """Force subcommand-name mode even while `version` is the only command
    (Typer otherwise collapses a single-command app into a no-subcommand
    CLI, which breaks `python -m app version` once more commands land)."""


@app.command()
def version() -> None:
    """Print the application version."""
    typer.echo("0.1.0")


if __name__ == "__main__":
    app()
