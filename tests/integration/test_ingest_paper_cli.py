import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()
FIXTURE_JPG = Path("tests/fixtures/existing_paper/main/page_1.jpg").resolve()


def test_ingest_paper_writes_artifacts_for_a_single_page_jpg(tmp_path):
    result = runner.invoke(
        app, ["ingest-paper", str(FIXTURE_JPG), "--storage-root", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output

    run_dirs = list(tmp_path.iterdir())
    assert len(run_dirs) == 1
    page_dir = run_dirs[0] / "page_01"

    assert (page_dir / "01_original.png").exists()
    assert (page_dir / "02_document_detected.png").exists()

    report = json.loads((page_dir / "02b_quality_report.json").read_text())
    assert report["verdict"] in ("pass", "flagged", "fail")


def test_ingest_paper_prints_observability_output_per_page(tmp_path):
    result = runner.invoke(
        app, ["ingest-paper", str(FIXTURE_JPG), "--storage-root", str(tmp_path)]
    )

    assert "Page 1" in result.output
