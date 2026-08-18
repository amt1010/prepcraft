"""CLI entry point. Every pipeline stage gets its own command here as it's
built (Phase 2+: ingest-paper, clean-paper, extract-questions, ...) so each
stage is runnable and inspectable independently, per PIPELINE.md.
"""

from dataclasses import asdict
from pathlib import Path

import typer

from app.backend.core.config import load_config
from app.backend.core.ids import new_id
from app.backend.core.secrets import Secrets
from app.backend.ingestion.image_loader import load_pages
from app.backend.ingestion.page_detector import detect_page
from app.backend.preprocessing.annotation_detector import detect_annotations
from app.backend.preprocessing.annotation_remover import remove_annotations
from app.backend.preprocessing.enhancement import enhance_image
from app.backend.preprocessing.perspective import correct_perspective
from app.backend.preprocessing.quality_gate import (
    evaluate_quality,
    measure_sharpness,
    measure_skew_degrees,
)
from app.backend.providers.vision import ClaudeVisionProvider
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


@app.command(name="clean-paper")
def clean_paper(run_id: str, storage_root: Path = Path("data/processed")) -> None:
    """Load a previously ingested run's detected pages, correct residual
    rotation, fix lighting, detect and remove handwritten/marked
    annotations, and write the cleaned artifacts."""
    store = ArtifactStore(storage_root, run_id)
    pages = store.list_pages()
    if not pages:
        typer.echo(f"No pages found for run {run_id} under {storage_root}")
        raise typer.Exit(code=1)

    secrets = Secrets()
    vision_provider = (
        ClaudeVisionProvider(api_key=secrets.anthropic_api_key)
        if secrets.anthropic_api_key
        else None
    )

    for index in pages:
        detected = store.load_image(index, "02_document_detected")

        corrected = correct_perspective(detected)
        store.save_image(index, "03_perspective_corrected", corrected)

        enhanced = enhance_image(corrected)
        store.save_image(index, "04_enhanced", enhanced)

        annotation_result = detect_annotations(enhanced, vision_provider=vision_provider)
        mask_image = (annotation_result.mask * 255).astype("uint8")
        store.save_image(index, "05_annotation_mask", mask_image)

        cleaned = remove_annotations(enhanced, annotation_result.mask)
        store.save_image(index, "06_cleaned", cleaned)

        typer.echo(
            f"[{index}] cleaned — {int(annotation_result.mask.sum())} annotation pixels removed"
        )

    typer.echo(f"Cleaned artifacts written to {store.run_dir}")


if __name__ == "__main__":
    app()
