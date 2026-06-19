import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from foundry import __version__
from foundry.api import router
from foundry.core.config import Settings, get_settings
from foundry.core.container import Container
from foundry.core.errors import FoundryError

logger = logging.getLogger("foundry")


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = Container.build(app_settings)
        app.state.container = container
        await container.startup()
        yield
        await container.shutdown()

    app = FastAPI(
        title=app_settings.app_name,
        version=__version__,
        description=(
            "Authentication-free PoC API for LangChain RAG, TAG, CAG, provider keys, "
            "pipeline versions, and deployments. Do not expose this PoC directly to the internet."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix=app_settings.api_prefix)

    @app.exception_handler(FoundryError)
    async def foundry_error_handler(_: Request, exc: FoundryError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Internal server error"}},
        )

    return app


app = create_app()
