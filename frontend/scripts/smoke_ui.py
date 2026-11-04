"""Optional real UI smoke test against the locally running frontend and API.

Uses a disposable API/database, synthetic data, and the local demo adapter.
The real personal workspace is never modified. Run after starting the frontend:
  .venv/Scripts/python.exe frontend/scripts/smoke_ui.py
Set PLAYWRIGHT_BROWSERS_PATH if Chromium was installed in a custom directory.
"""

from __future__ import annotations

import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "storage" / "reports"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
WEB = os.environ.get("UI_SMOKE_WEB", "http://localhost:3000")


@contextmanager
def isolated_api():
    with tempfile.TemporaryDirectory(prefix="ui-smoke-", dir=ROOT / "storage") as directory:
        scratch = Path(directory)
        context = scratch / "context"
        context.mkdir()
        for name in ("candidate_context.md", "custom_instructions.md"):
            (context / name).write_text("", encoding="utf-8")
        for name in ("job_preferences.yaml", "application_rules.yaml"):
            (context / name).write_text("{}\n", encoding="utf-8")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = {**os.environ, "DATABASE_URL": f"sqlite:///{(scratch / 'test.db').as_posix()}",
               "STORAGE_DIR": str(scratch / "storage"), "CONTEXT_DIR": str(context),
               "SECRET_KEY": secrets.token_urlsafe(48), "INLINE_TASKS": "true", "LLM_ENDPOINT": "",
               "ENABLE_EMBEDDINGS": "false", "LOCAL_USER_ID": "", "CORS_ORIGINS": WEB.rstrip("/")}
        with (scratch / "server.log").open("w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
                           cwd=ROOT, env=env, stdout=log, stderr=log, check=True)
            server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                       "--port", str(port), "--no-access-log"], cwd=ROOT, env=env, stdout=log, stderr=log)
            try:
                address = f"http://127.0.0.1:{port}"
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("El backend aislado de pruebas no pudo arrancar")
                    try:
                        if httpx.get(address + "/health", timeout=0.5).status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    time.sleep(0.2)
                else:
                    raise RuntimeError("Tiempo agotado al arrancar el backend aislado")
                yield address + "/api/v1"
            finally:
                server.terminate()
                server.wait(timeout=10)


def run_smoke(api_url: str) -> None:
    email = f"ui-smoke-{uuid4().hex[:12]}@example.test"
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, device_scale_factor=1)
        page.set_default_timeout(25000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        portal_requests: list[str] = []
        page.on("request", lambda request: portal_requests.append(request.url)
                if any(host in request.url for host in ("linkedin.com", "computrabajo.com")) else None)
        def proxy(route):
            assert "authorization" not in route.request.headers
            suffix = route.request.url.split("/api/v1", 1)[1]
            response = route.fetch(url=api_url + suffix, max_redirects=0)
            route.fulfill(response=response)
        page.route("**/api/v1/**", proxy)
        try:
            page.goto(WEB, wait_until="networkidle")
            expect(page.get_by_role("heading", name=re.compile("Tu próximo paso empieza aquí"))).to_be_visible()
            expect(page.get_by_role("button", name="Cerrar sesión", exact=True)).to_have_count(0)
            assert page.evaluate("sessionStorage.length") == 0
            print("PASS dashboard opens directly without login, password or session token")

            page.get_by_role("button", name="Mi perfil", exact=True).click()
            page.get_by_label("Nombre completo", exact=True).fill("Candidato de Prueba")
            page.get_by_label("Correo electrónico", exact=True).fill(email)
            page.get_by_label("Título profesional", exact=True).fill("Backend Developer")
            page.get_by_role("button", name="Guardar cambios", exact=True).click()
            expect(page.locator(".heading-actions")).to_contain_text("Pendiente")
            page.reload(wait_until="networkidle")
            page.get_by_role("button", name="Mi perfil", exact=True).click()
            expect(page.get_by_label("Nombre completo", exact=True)).to_have_value("Candidato de Prueba")
            expect(page.get_by_label("Correo electrónico", exact=True)).to_have_value(email)
            print("PASS manual profile entry without a CV and persistence after reload")
            cv = (
                f"Nombre: Candidato de Prueba\nCorreo: {email}\n"
                "Titulo: Backend Developer\nUbicacion: Bogota, Colombia\n"
                "Habilidades: Python, FastAPI, PostgreSQL, Docker, React, TypeScript\n"
                "Experiencia: 5 anos de experiencia en desarrollo de APIs Python.\n"
                "Resumen: Desarrollo backend con Python, FastAPI y PostgreSQL.\n"
            )
            page.locator('input[type="file"]').set_input_files({
                "name": "candidato-prueba.txt", "mimeType": "text/plain", "buffer": cv.encode("utf-8")
            })
            expect(page.get_by_role("heading", name="Perfil profesional", exact=True)).to_be_visible()
            page.get_by_label("Años de experiencia confirmados", exact=True).fill("5")
            page.get_by_role("button", name="Guardar y aprobar perfil", exact=True).click()
            expect(page.locator(".heading-actions")).to_contain_text("Revisado")
            print("PASS CV upload, profile edit and review")

            page.get_by_role("button", name="Contexto y reglas", exact=True).click()
            page.get_by_role("tab", name="Reglas", exact=True).click()
            page.get_by_text("Consentimiento para compartir datos profesionales", exact=True).click()
            page.get_by_role("button", name="Guardar contexto", exact=True).click()
            expect(page.get_by_role("button", name="Guardar contexto", exact=True)).to_be_disabled()
            page.get_by_role("button", name="Activar planificación", exact=True).click()
            expect(page.locator(".sidebar-status")).to_contain_text("activa")
            print("PASS editable rules, consent and planning")

            page.get_by_role("button", name="Oportunidades", exact=True).click()
            page.get_by_label("Fuente de vacantes", exact=True).select_option("demo")
            page.get_by_role("button", name="Buscar ofertas", exact=True).click()
            expect(page.locator(".job-card")).to_have_count(3)
            page.get_by_role("button", name=re.compile(r"\[PRUEBA\] Backend Developer")).click()
            expect(page.get_by_role("dialog")).to_be_visible()
            page.get_by_role("button", name="Preparar candidatura", exact=True).click()
            expect(page.get_by_role("heading", name="Cada candidatura cuenta una historia.")).to_be_visible()
            page.locator("tbody tr").filter(has_text="[PRUEBA] Backend Developer").get_by_role(
                "button", name="Revisar", exact=True
            ).click()
            expect(page.get_by_role("dialog")).to_contain_text("Carta de presentación")
            page.get_by_role("button", name="Aprobar contenido", exact=True).click()
            page.get_by_role("button", name="Enviar al proveedor de pruebas", exact=True).click()
            expect(page.get_by_role("dialog").locator(".application-detail-status")).to_contain_text("Confirmada")
            expect(page.get_by_role("dialog")).to_contain_text("DEMO-")
            page.get_by_role("button", name="Cerrar diálogo", exact=True).click()
            print("PASS demo search, matching, draft, approval and confirmed sandbox submission")

            def import_offer(source: str, url: str, title: str, company: str) -> None:
                page.get_by_role("button", name="Oportunidades", exact=True).click()
                page.get_by_role("button", name="Importar oferta", exact=True).click()
                dialog = page.get_by_role("dialog")
                dialog.get_by_label("Portal de la oferta", exact=True).select_option(source)
                dialog.get_by_label("Enlace original de la oferta", exact=True).fill(url)
                dialog.get_by_label("Cargo de la oferta", exact=True).fill(title)
                dialog.get_by_label("Empresa de la oferta", exact=True).fill(company)
                dialog.get_by_label("Texto de la oferta o alerta", exact=True).fill(
                    "Desarrollo de APIs con Python, FastAPI y PostgreSQL. Trabajo colaborativo y desarrollo de software."
                )
                dialog.get_by_label("Modalidad publicada", exact=True).select_option("remote")
                dialog.locator("summary").click()
                dialog.get_by_label("Salario publicado desde", exact=True).fill("7500000")
                dialog.get_by_label("Salario publicado hasta", exact=True).fill("8500000")
                if source == "linkedin":
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    page.screenshot(path=str(ARTIFACTS / "ui-assisted-import-mobile.png"), full_page=True)
                    page.set_viewport_size({"width": 1440, "height": 1050})
                dialog.get_by_role("button", name="Guardar y analizar", exact=True).click()
                expect(page.get_by_role("dialog")).to_contain_text("Compatibilidad con tu perfil")
                expect(page.get_by_role("dialog")).to_contain_text("Texto aportado por ti")

            import_offer("linkedin", "https://www.linkedin.com/jobs/view/1234567890/?trackingId=example",
                         "Senior Python Developer", "Synthetic LinkedIn Employer")
            expect(page.get_by_role("link", name="Abrir en linkedin", exact=True)).to_have_attribute(
                "href", "https://www.linkedin.com/jobs/view/1234567890")
            page.get_by_role("button", name="Preparar candidatura", exact=True).click()
            page.locator("tbody tr").filter(has_text="Synthetic LinkedIn Employer").get_by_role(
                "button", name="Revisar", exact=True).click()
            page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=WEB)
            page.get_by_role("button", name="Copiar carta", exact=True).click()
            expect(page.get_by_text("Carta copiada al portapapeles.", exact=True)).to_be_visible()
            assert "Python" in page.evaluate("navigator.clipboard.readText()")
            expect(page.get_by_role("link", name="Abrir oferta original", exact=True)).to_have_attribute(
                "href", "https://www.linkedin.com/jobs/view/1234567890")
            page.get_by_role("button", name="Aprobar contenido", exact=True).click()
            page.get_by_role("button", name="Registrar formulario enviado", exact=True).click()
            expect(page.get_by_role("dialog").locator(".application-detail-status")).to_contain_text("Enviada")
            page.get_by_text("La plataforma confirmó que recibió mi candidatura.", exact=True).click()
            page.get_by_role("button", name="Registrar confirmación", exact=True).click()
            expect(page.get_by_role("dialog").locator(".application-detail-status")).to_contain_text("Confirmada")
            page.get_by_role("button", name="Cerrar diálogo", exact=True).click()
            print("PASS LinkedIn assisted import, clipboard, original link and user-reported submission")

            import_offer("computrabajo", "https://co.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-synthetic-123ABC",
                         "Python Developer", "Synthetic Computrabajo Employer")
            page.get_by_role("button", name="Completar datos", exact=True).click()
            page.get_by_label("Ubicación publicada", exact=True).fill("Bogota, Colombia")
            page.get_by_role("button", name="Guardar cambios y analizar", exact=True).click()
            expect(page.get_by_role("dialog")).to_contain_text("Bogota, Colombia")
            page.get_by_role("button", name="Cerrar diálogo", exact=True).click()
            expect(page.locator(".job-card")).to_have_count(5)
            import_offer("linkedin", "https://www.linkedin.com/jobs/view/1234567890",
                         "Senior Python Developer", "Synthetic LinkedIn Employer")
            page.get_by_role("button", name="Cerrar diálogo", exact=True).click()
            expect(page.locator(".job-card")).to_have_count(5)
            assert not portal_requests, portal_requests
            print("PASS Computrabajo import, duplicate detection and zero portal access")

            page.get_by_role("button", name="Vista general", exact=True).click()
            expect(page.locator(".preview-job")).to_have_count(3)
            expect(page.locator(".metric-card").filter(has_text="Envíos registrados")).to_contain_text(
                "1 reales · 1 de prueba"
            )
            if page.get_by_role("button", name="Cerrar notificación", exact=True).is_visible():
                page.get_by_role("button", name="Cerrar notificación", exact=True).click()
            page.screenshot(path=str(ARTIFACTS / "ui-dashboard-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 1")
            page.screenshot(path=str(ARTIFACTS / "ui-dashboard-mobile.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile layout overflows horizontally"
            page.get_by_role("button", name="Abrir menú", exact=True).click()
            page.get_by_role("button", name="Mi perfil", exact=True).click()
            expect(page.get_by_role("heading", name="Tu experiencia, con tu propia voz.")).to_be_visible()
            page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 1")
            page.screenshot(path=str(ARTIFACTS / "ui-profile-mobile.png"), full_page=True)
            page.get_by_role("button", name="Parar", exact=True).click()
            expect(page.locator(".sidebar-status")).to_contain_text("pausa")
            assert not errors, f"Browser runtime errors: {errors}"
            print("PASS responsive mobile navigation, emergency stop, zero browser runtime errors")
        except Exception:
            page.screenshot(path=str(ARTIFACTS / "ui-smoke-failure.png"), full_page=True)
            raise
        finally:
            browser.close()
            print("PASS isolated test data discarded; personal workspace untouched")


def main() -> None:
    with isolated_api() as api_url:
        run_smoke(api_url)


if __name__ == "__main__":
    main()
