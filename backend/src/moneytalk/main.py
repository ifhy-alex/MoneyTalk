from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from moneytalk.api import router as api_router
from moneytalk.config import get_settings
from moneytalk.log import configure_logging


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
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
