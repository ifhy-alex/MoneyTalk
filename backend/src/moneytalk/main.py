from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from moneytalk.api import router as api_router
from moneytalk.config import get_settings
from moneytalk.log import configure_logging

# Única ruta de la API a la que se llega navegando desde otro sitio: la vuelta de Google.
_CROSS_SITE_NAVIGATION_OK = {"/api/gmail/callback"}


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Sirve el build de Vite; cualquier ruta que no sea /api cae en index.html (SPA)."""
    root = static_dir.resolve()
    index = root / "index.html"
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        # Sin caché: tras actualizar la app, un index.html viejo apuntaría a assets que ya
        # no existen y la ventana quedaría en blanco. Los assets llevan hash y sí se cachean.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="MoneyTalk",
        description=(
            "Finanzas personales e inversiones. "
            "Las señales de inversión NO son asesoría financiera."
        ),
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def reject_cross_site(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """La API escucha en localhost sin login: cualquier página abierta en el navegador
        podría mandarle peticiones "simples" (sin preflight de CORS), como un <img> o un
        formulario. Se rechazan las que el navegador marca como de otro sitio."""
        path = request.url.path
        if path.startswith("/api/") and request.headers.get("sec-fetch-site") == "cross-site":
            navigating = request.headers.get("sec-fetch-mode") == "navigate"
            if not (navigating and path in _CROSS_SITE_NAVIGATION_OK):
                return JSONResponse({"detail": "Petición de otro sitio rechazada"}, status_code=403)
        return await call_next(request)

    app.include_router(api_router, prefix="/api")
    if settings.static_dir and (settings.static_dir / "index.html").exists():
        _mount_frontend(app, settings.static_dir)
    return app


app = create_app()
