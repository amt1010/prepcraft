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


def test_load_image_round_trips_a_saved_image(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    image[:, :, 2] = 200  # a distinct tint in the red channel (BGR)

    store.save_image(1, "01_original", image)
    loaded = store.load_image(1, "01_original")

    assert loaded.shape == image.shape
    assert np.array_equal(loaded, image)


def test_list_pages_returns_sorted_page_numbers(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")
    image = np.zeros((5, 5, 3), dtype=np.uint8)

    store.save_image(2, "01_original", image)
    store.save_image(1, "01_original", image)

    assert store.list_pages() == [1, 2]


def test_list_pages_returns_empty_list_for_a_run_that_does_not_exist(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-MISSING")

    assert store.list_pages() == []


def test_save_run_json_writes_to_the_run_root_not_a_page_dir(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")

    path = store.save_run_json("09_questions", {"questions": []})

    assert path == tmp_path / "RUN-001" / "09_questions.json"
    assert json.loads(path.read_text()) == {"questions": []}


def test_load_run_json_round_trips_a_saved_run_json(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")
    store.save_run_json("09_questions", {"questions": [{"question_number": "1a"}]})

    loaded = store.load_run_json("09_questions")

    assert loaded == {"questions": [{"question_number": "1a"}]}
