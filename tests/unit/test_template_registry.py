from app.backend.models.question import QuestionType
from app.backend.questions.template_registry import TEMPLATES, get_templates


def test_every_question_type_has_at_least_one_template():
    for question_type in QuestionType:
        templates = get_templates(question_type)
        assert templates, f"no seed template for {question_type}"
        assert all(t.question_type == question_type for t in templates)


def test_get_templates_without_a_filter_returns_everything():
    assert get_templates() == TEMPLATES


def test_template_ids_are_unique():
    ids = [t.id for t in TEMPLATES]
    assert len(ids) == len(set(ids))


def test_multiple_choice_templates_declare_distractor_offsets():
    for template in get_templates(QuestionType.MULTIPLE_CHOICE):
        assert template.distractor_offsets
