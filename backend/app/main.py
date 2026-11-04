from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import applications, context, dashboard, jobs, profile, workspace
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
settings = get_settings()
app = FastAPI(
    title="AutoJob AI",
    version="0.1.0",
    description="Asistente privado de búsqueda laboral basado en hechos verificables",
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "backend", "testserver"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def private_responses(request: Request, call_next):  # type: ignore[no-untyped-def]
    origin = request.headers.get("origin")
    allowed = {value.strip().rstrip("/") for value in settings.cors_origins.split(",")}
    if (
        origin
        and origin.rstrip("/") not in allowed
        and origin.rstrip("/") != str(request.base_url).rstrip("/")
    ):
        return JSONResponse(
            status_code=403, content={"detail": "El espacio personal sólo admite el origen local configurado"}
        )
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(ValidationError)
async def invalid_stored_data(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "Configuración o datos inválidos. Revisa los campos y archivos de contexto."},
    )


for router in (
    workspace.router,
    profile.router,
    context.router,
    jobs.router,
    applications.router,
    dashboard.router,
):
    app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "autojob-ai"}
