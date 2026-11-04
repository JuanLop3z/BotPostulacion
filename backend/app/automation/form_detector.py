"""Inspect only known controls. Do not infer answers to hiring or legal questions."""

from typing import Any


class NeedsHumanIntervention(ValueError):
    pass


CAPTCHA_SELECTOR = (
    'iframe[src*="recaptcha"], iframe[src*="hcaptcha"], iframe[src*="challenges.cloudflare"], '
    '[class*="g-recaptcha"], [class*="h-captcha"], input[name*="captcha"], [data-captcha]'
)
AUTH_SELECTOR = 'input[type="password"], input[autocomplete="one-time-code"]'


def inspect_form(page: Any, answers: dict[str, str]) -> list[dict[str, Any]]:
    if page.locator(CAPTCHA_SELECTOR).count():
        raise NeedsHumanIntervention("Se detectó CAPTCHA; complete el proceso manualmente.")
    if page.locator(AUTH_SELECTOR).count():
        raise NeedsHumanIntervention("La página requiere autenticación o verificación humana.")
    controls: list[dict[str, Any]] = page.locator("input, textarea, select").evaluate_all(
        "elements => elements.map(el => ({name: el.name, type: el.type, "
        "required: el.required, disabled: el.disabled, value: el.value, "
        "tag: el.tagName.toLowerCase()}))"
    )
    for control in controls:
        if control.get("disabled") or control.get("type") in {"submit", "button", "hidden"}:
            continue
        name = str(control.get("name") or "")
        if control.get("required") and (not name or not answers.get(name)):
            raise NeedsHumanIntervention("Hay una pregunta obligatoria sin respuesta validada.")
        if control.get("type") in {"file", "checkbox", "radio"} and control.get("required"):
            raise NeedsHumanIntervention("Este control obligatorio requiere revisión humana.")
    return controls
