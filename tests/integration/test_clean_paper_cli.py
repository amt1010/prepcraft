import numpy as np
from typer.testing import CliRunner

from app.backend.storage.artifact_store import ArtifactStore
from app.cli import app

runner = CliRunner()


def test_clean_paper_writes_all_expected_artifacts_for_each_page(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    store = ArtifactStore(tmp_path, "RUN-TEST")
    page = np.full((100, 100, 3), 255, dtype=np.uint8)
    page[40:60, 40:60] = (30, 30, 200)  # a red mark to clean up
    store.save_image(1, "02_document_detected", page)

    result = runner.invoke(app, ["clean-paper", "RUN-TEST", "--storage-root", str(tmp_path)])

    assert result.exit_code == 0, result.output

    page_dir = tmp_path / "RUN-TEST" / "page_01"
    assert (page_dir / "03_perspective_corrected.png").exists()
    assert (page_dir / "04_enhanced.png").exists()
    assert (page_dir / "05_annotation_mask.png").exists()
    assert (page_dir / "06_cleaned.png").exists()


def test_clean_paper_exits_with_an_error_when_the_run_has_no_pages(tmp_path):
    result = runner.invoke(app, ["clean-paper", "RUN-MISSING", "--storage-root", str(tmp_path)])

    assert result.exit_code == 1
