"""CLI entry point. Every pipeline stage gets its own command here as it's
built (Phase 2+: ingest-paper, clean-paper, extract-questions, ...) so each
stage is runnable and inspectable independently, per PIPELINE.md.
"""

from dataclasses import asdict
from pathlib import Path

import typer

from app.backend.core.config import load_config
from app.backend.core.ids import new_id
from app.backend.ingestion.image_loader import load_pages
from app.backend.ingestion.page_detector import detect_page
from app.backend.preprocessing.quality_gate import (
    evaluate_quality,
    measure_sharpness,
    measure_skew_degrees,
)
from app.backend.storage.artifact_store import ArtifactStore

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


@app.command(name="ingest-paper")
def ingest_paper(
    path: Path,
    storage_root: Path = Path("data/processed"),
    config_path: Path = Path("config.yaml"),
) -> None:
    """Ingest a paper (PDF/JPG/PNG): load pages, detect page boundaries,
    run the image quality gate, and write inspectable artifacts."""
    cfg = load_config(config_path) if config_path.exists() else None
    max_skew = cfg.quality.max_skew_degrees if cfg else 20.0
    min_sharpness = cfg.quality.min_sharpness if cfg else 100.0

    run_id = new_id("RUN")
    store = ArtifactStore(storage_root, run_id)
    pages = load_pages(path)
    typer.echo(f"[1/2] Loaded {len(pages)} page(s)  run_id={run_id}")

    for index, page in enumerate(pages, start=1):
        store.save_image(index, "01_original", page)
        detection = detect_page(page)
        store.save_image(index, "02_document_detected", detection.image)

        sharpness = measure_sharpness(detection.image)
        skew = measure_skew_degrees(detection.corners)
        report = evaluate_quality(skew, sharpness, max_skew, min_sharpness)
        store.save_json(index, "02b_quality_report", asdict(report) | {"page": index})

        symbol = {"pass": "OK", "flagged": "~", "fail": "X"}[report.verdict]
        typer.echo(
            f"[2/2] Page {index}: quality {symbol} ({report.verdict}, "
            f"skew={skew:.1f} deg, sharpness={sharpness:.0f})"
        )

    typer.echo(f"Artifacts written to {store.run_dir}")


if __name__ == "__main__":
    app()
