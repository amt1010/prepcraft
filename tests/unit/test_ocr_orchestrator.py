from app.backend.ocr.orchestrator import extract_text_with_fallback
from app.backend.providers.ocr import OCRResult, OCRWord


class _FakeProvider:
    def __init__(self, result: OCRResult):
        self.result = result
        self.calls = 0

    def extract_text(self, image: bytes) -> OCRResult:
        self.calls += 1
        return self.result


def test_returns_primary_result_when_confidence_is_high():
    primary = _FakeProvider(
        OCRResult(words=[OCRWord(text="a", confidence=95, left=0, top=0, width=1, height=1)], full_text="a")
    )
    fallback = _FakeProvider(OCRResult(words=[], full_text="fallback"))

    result = extract_text_with_fallback(b"img", primary, fallback)

    assert result.full_text == "a"
    assert fallback.calls == 0


def test_calls_fallback_when_mean_confidence_is_below_threshold():
    primary = _FakeProvider(
        OCRResult(words=[OCRWord(text="a", confidence=10, left=0, top=0, width=1, height=1)], full_text="a")
    )
    fallback = _FakeProvider(OCRResult(words=[], full_text="fallback"))

    result = extract_text_with_fallback(b"img", primary, fallback, confidence_threshold=60.0)

    assert result.full_text == "fallback"
    assert fallback.calls == 1


def test_returns_primary_result_when_no_fallback_is_configured():
    primary = _FakeProvider(
        OCRResult(words=[OCRWord(text="a", confidence=5, left=0, top=0, width=1, height=1)], full_text="a")
    )

    result = extract_text_with_fallback(b"img", primary, fallback=None)

    assert result.full_text == "a"


def test_returns_primary_result_unchanged_when_it_found_no_words_at_all():
    primary = _FakeProvider(OCRResult(words=[], full_text=""))
    fallback = _FakeProvider(OCRResult(words=[], full_text="fallback"))

    result = extract_text_with_fallback(b"img", primary, fallback)

    assert result.full_text == ""
    assert fallback.calls == 0
