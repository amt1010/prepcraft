import numpy as np
from typer.testing import CliRunner

from app.backend.storage.artifact_store import ArtifactStore
from app.cli import app

runner = CliRunner()


def test_extract_questions_writes_all_expected_artifacts(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    store = ArtifactStore(tmp_path, "RUN-TEST")
    page = np.full((200, 800, 3), 255, dtype=np.uint8)
    store.save_image(1, "06_cleaned", page)

    result = runner.invoke(app, ["extract-questions", "RUN-TEST", "--storage-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    page_dir = tmp_path / "RUN-TEST" / "page_01"
    assert (page_dir / "07_ocr.json").exists()
    assert (page_dir / "08_layout.json").exists()
    assert (tmp_path / "RUN-TEST" / "09_questions.json").exists()


def test_extract_questions_exits_with_an_error_when_the_run_has_no_pages(tmp_path):
    result = runner.invoke(app, ["extract-questions", "RUN-MISSING", "--storage-root", str(tmp_path)])

    assert result.exit_code == 1
