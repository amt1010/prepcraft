import json

import numpy as np

from app.backend.storage.artifact_store import ArtifactStore


def test_save_image_writes_to_the_page_scoped_path(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")
    image = np.zeros((10, 10, 3), dtype=np.uint8)

    path = store.save_image(1, "01_original", image)

    assert path == tmp_path / "RUN-001" / "page_01" / "01_original.png"
    assert path.exists()


def test_save_json_writes_readable_json_to_the_page_scoped_path(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")

    path = store.save_json(2, "02b_quality_report", {"verdict": "pass"})

    assert path == tmp_path / "RUN-001" / "page_02" / "02b_quality_report.json"
    assert json.loads(path.read_text()) == {"verdict": "pass"}


def test_different_pages_get_separate_directories(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")
    image = np.zeros((5, 5, 3), dtype=np.uint8)

    store.save_image(1, "01_original", image)
    store.save_image(2, "01_original", image)

    assert (tmp_path / "RUN-001" / "page_01" / "01_original.png").exists()
    assert (tmp_path / "RUN-001" / "page_02" / "01_original.png").exists()
