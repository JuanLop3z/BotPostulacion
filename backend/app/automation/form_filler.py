"""Fill allowlisted text fields; CSS selectors are never interpolated from remote HTML."""

from typing import Any

from app.automation.form_detector import inspect_form

SAFE_TEXT_TYPES = {"text", "email", "tel", "url", "number", "textarea"}


def fill_known_fields(page: Any, answers: dict[str, str]) -> list[str]:
    controls = inspect_form(page, answers)
    filled: list[str] = []
    for control in controls:
        name = str(control.get("name") or "")
        if control.get("disabled") or name not in answers:
            continue
        if control.get("type") not in SAFE_TEXT_TYPES:
            continue
        # Filter nodes using evaluate; names can contain quotes/brackets and may
        # never become arbitrary CSS or code.
        page.locator("input, textarea").evaluate_all(
            "(elements, item) => { for (const el of elements) { if (el.name === item.name) { "
            "const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; "
            "const setter = Object.getOwnPropertyDescriptor(proto, 'value').set; "
            "setter.call(el, item.value); el.dispatchEvent(new Event('input', {bubbles:true})); "
            "el.dispatchEvent(new Event('change', {bubbles:true})); } } }",
            {"name": name, "value": answers[name]},
        )
        filled.append(name)
    return filled
