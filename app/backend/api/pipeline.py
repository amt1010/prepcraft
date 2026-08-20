"""End-to-end pipeline orchestration for the minimal manual-testing web
page (api/server.py). Thin composition of already-built, already-tested
modules — mirrors app/cli.py's ingest-paper/clean-paper/extract-questions
stage sequence exactly (verified against that file), then adds
Workflow A's 1:1 regeneration and rendering. No new pipeline logic."""

import random
from pathlib import Path

import cv2
import pymupdf

from app.backend.answer_key.builder import build_answer_key
from app.backend.core.config import load_config
from app.backend.core.secrets import Secrets
from app.backend.generation.paper_generator import regenerate_paper
from app.backend.ingestion.image_loader import load_pages
from app.backend.ingestion.page_detector import detect_page
from app.backend.ocr.layout_analysis import group_by_question_number, group_text_by_question_number
from app.backend.ocr.orchestrator import extract_text_with_fallback
from app.backend.preprocessing.annotation_detector import detect_annotations
from app.backend.preprocessing.annotation_remover import remove_annotations
from app.backend.preprocessing.enhancement import enhance_image
from app.backend.preprocessing.perspective import correct_perspective
from app.backend.providers.ocr.claude_provider import ClaudeOCRProvider
from app.backend.providers.ocr.tesseract_provider import TesseractOCRProvider
from app.backend.providers.text_generation import ClaudeTextGenerationProvider
from app.backend.providers.vision import ClaudeVisionProvider
from app.backend.questions.extraction import extract_questions
from app.backend.questions.paper_assembly import assemble_paper_from_extracted
from app.backend.rendering.renderer import render_answer_sheet, render_question_paper


def _build_providers(
    config_path: Path,
) -> tuple[
    ClaudeVisionProvider | None, ClaudeOCRProvider | None, ClaudeTextGenerationProvider | None
]:
    cfg = load_config(config_path) if config_path.exists() else None
    secrets = Secrets()
    if not secrets.anthropic_api_key:
        return None, None, None
    vision_provider = ClaudeVisionProvider(api_key=secrets.anthropic_api_key)
    ocr_fallback = ClaudeOCRProvider(
        api_key=secrets.anthropic_api_key,
        model=cfg.models.ocr_fallback if cfg else "claude-haiku-4-5",
    )
    text_provider = ClaudeTextGenerationProvider(
        api_key=secrets.anthropic_api_key,
        model=cfg.models.question_classification if cfg else "claude-sonnet-5",
    )
    return vision_provider, ocr_fallback, text_provider


def run_full_pipeline(
    image_path: Path,
    subject: str,
    class_standard: str,
    duration_minutes: int,
    output_root: Path = Path("data/generated"),
    config_path: Path = Path("config.yaml"),
    use_real_providers: bool = True,
) -> tuple[Path, Path]:
    if use_real_providers:
        vision_provider, ocr_fallback, text_provider = _build_providers(config_path)
    else:
        vision_provider = ocr_fallback = text_provider = None

    if image_path.suffix.lower() == ".pdf":
        pdf_text = "\n".join(page.get_text() for page in pymupdf.open(image_path))
        groups = group_text_by_question_number(pdf_text)
    else:
        pages = load_pages(image_path)
        groups = []
        for page in pages:
            detection = detect_page(page)
            corrected = correct_perspective(detection.image)
            enhanced = enhance_image(corrected)
            annotation_result = detect_annotations(enhanced, vision_provider=vision_provider)
            cleaned = remove_annotations(enhanced, annotation_result.mask)

            success, buffer = cv2.imencode(".png", cleaned)
            if not success:
                raise ValueError("failed to encode cleaned page as PNG")
            ocr_result = extract_text_with_fallback(
                buffer.tobytes(), TesseractOCRProvider(), ocr_fallback
            )
            groups.extend(group_by_question_number(ocr_result))
    extracted = extract_questions(groups, text_provider=text_provider)

    source_paper, source_questions = assemble_paper_from_extracted(
        subject=subject,
        class_standard=class_standard,
        duration_minutes=duration_minutes,
        extracted_questions=extracted,
    )
    generated_paper, generated_questions = regenerate_paper(
        source_paper, source_questions, rng=random.Random(), text_provider=text_provider
    )
    answer_key = build_answer_key(generated_paper, generated_questions)

    paper_dir = output_root / generated_paper.id
    question_paper_path = render_question_paper(
        generated_paper, generated_questions, paper_dir / "question_paper.pdf"
    )
    answer_sheet_path = render_answer_sheet(
        generated_paper, answer_key, paper_dir / "answer_sheet.pdf"
    )
    return question_paper_path, answer_sheet_path
