from app.backend.ocr.layout_analysis import (
    LayoutGroup,
    group_by_question_number,
    group_text_by_question_number,
)
from app.backend.providers.ocr import OCRResult, OCRWord


def _word(text: str, index: int) -> OCRWord:
    return OCRWord(text=text, confidence=90, left=index * 10, top=0, width=8, height=10)


def test_groups_words_after_a_top_level_number():
    words = [_word(w, i) for i, w in enumerate(["1.", "What", "is", "2+2?"])]
    ocr_result = OCRResult(words=words, full_text="1. What is 2+2?")

    groups = group_by_question_number(ocr_result)

    assert groups == [LayoutGroup(question_number="1", text="What is 2+2?")]


def test_starts_a_new_group_at_the_next_top_level_number():
    words = [_word(w, i) for i, w in enumerate(["1.", "a", "b", "2.", "c", "d"])]
    ocr_result = OCRResult(words=words, full_text="1. a b 2. c d")

    groups = group_by_question_number(ocr_result)

    assert [g.question_number for g in groups] == ["1", "2"]
    assert groups[0].text == "a b"
    assert groups[1].text == "c d"


def test_ignores_words_before_the_first_top_level_number():
    words = [_word(w, i) for i, w in enumerate(["Series:", "DWPS", "1.", "a"])]
    ocr_result = OCRResult(words=words, full_text="Series: DWPS 1. a")

    groups = group_by_question_number(ocr_result)

    assert len(groups) == 1
    assert groups[0].question_number == "1"


def test_returns_empty_list_when_no_top_level_numbers_found():
    words = [_word(w, i) for i, w in enumerate(["Series:", "DWPS"])]
    ocr_result = OCRResult(words=words, full_text="Series: DWPS")

    groups = group_by_question_number(ocr_result)

    assert groups == []


def test_does_not_treat_a_lettered_sub_part_marker_as_a_new_top_level_group():
    words = [_word(w, i) for i, w in enumerate(["1.", "a.", "405", "b.", "450"])]
    ocr_result = OCRResult(words=words, full_text="1. a. 405 b. 450")

    groups = group_by_question_number(ocr_result)

    assert len(groups) == 1
    assert groups[0].question_number == "1"
    assert groups[0].text == "a. 405 b. 450"


def test_groups_text_layer_questions_by_all_sections_in_source_order():
    text = """Worksheet
A. Fill in the blanks. (2 x 1 = 2)
1. 4 x 6 = ___
2. 7 x 8 = ___
B. Multiply. (1 x 2 = 2)
1. 24 x 3 = ___
C. Column method
1. 125 x 3 = ___
D. Word Problems
1. A school has 6 classrooms.
E. Think and Answer
1. Find the missing number.
"""

    groups = group_text_by_question_number(text)

    assert len(groups) == 6
    assert [group.section_name for group in groups] == [
        "A. Fill in the blanks. (2 x 1 = 2)",
        "A. Fill in the blanks. (2 x 1 = 2)",
        "B. Multiply. (1 x 2 = 2)",
        "C. Column method",
        "D. Word Problems",
        "E. Think and Answer",
    ]


def test_groups_the_real_multiplication_worksheet_into_all_53_questions():
    import pymupdf

    path = "input_data/Class_3_Multiplication_Combined_Worksheet.pdf"
    text = "\n".join(page.get_text() for page in pymupdf.open(path))

    groups = group_text_by_question_number(text)

    assert len(groups) == 53
    assert {group.section_name for group in groups} == {
        "A. Fill in the blanks. (25 × 1 = 25)",
        "B. Multiply. (5 × 2 = 10)",
        "C. Multiply using the column method. (5 × 2 = 10)",
        "D. Word Problems",
        "E. Think and Answer",
    }
