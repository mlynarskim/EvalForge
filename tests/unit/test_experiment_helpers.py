import pytest

from app.services.experiment_service import extract_variables, render_template


def test_template_rendering_supports_nested_values() -> None:
    template = "Hello {{ customer.name }}, order {{order.id}} is ready."
    rendered = render_template(template, {"customer": {"name": "Ada"}, "order": {"id": 42}})
    assert rendered == "Hello Ada, order 42 is ready."
    assert extract_variables(template) == ["customer.name", "order.id"]


def test_template_rendering_never_executes_code() -> None:
    template = "{{__import__('os').system('false')}}"
    assert render_template(template, {}) == template


def test_template_rendering_rejects_missing_values() -> None:
    with pytest.raises(ValueError, match="Missing template variable"):
        render_template("{{missing}}", {})
