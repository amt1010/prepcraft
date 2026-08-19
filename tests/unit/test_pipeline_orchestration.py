"""Exercises run_full_pipeline's real wiring (real Tesseract OCR, real
OpenCV image processing — no network calls) against the golden mental_maths
fixture, with use_real_providers=False forcing the no-classification path
regardless of this repo's own configured ANTHROPIC_API_KEY. This suite
must stay free and fast; Task 5's manual browser verification (real
providers, real classification) is what proves the happy-path end-to-end
result. This test proves the unclassified-fallback path fails the way
questions/paper_assembly.py documents (ValueError on marks/topic/
difficulty missing) rather than silently producing a garbage Paper."""

from pathlib import Path

import pytest

from app.backend.api.pipeline import run_full_pipeline


def test_run_full_pipeline_raises_on_unclassified_extraction(tmp_path):
    with pytest.raises(ValueError):
        run_full_pipeline(
            Path("tests/fixtures/existing_paper/mental_maths/page_1.jpg"),
            subject="Mathematics",
            class_standard="III",
            duration_minutes=20,
            output_root=tmp_path,
            use_real_providers=False,
        )
