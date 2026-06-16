"""FastAPI application factory for Hephaestus Studio."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from hephaestus.models import ModelProvider
from hephaestus.studio.api import router
from hephaestus.studio.security import (
    DEFAULT_STUDIO_HOST,
    DEFAULT_STUDIO_PORT,
    allowed_cors_origins,
)
from hephaestus.studio.security import (
    resolve_static_dir as resolve_static_assets_dir,
)
from hephaestus.studio.services import StudioService


class StudioStaticFiles(StaticFiles):
    """Serve exported Next assets and fall back to index.html for app routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code == 404 and "." not in Path(path).name:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and "." not in Path(path).name:
            return await super().get_response("index.html", scope)
        return response


def create_studio_app(
    database_path: Path | str | None = None,
    *,
    host: str = DEFAULT_STUDIO_HOST,
    port: int = DEFAULT_STUDIO_PORT,
    static_dir: Path | str | None = None,
    provider: ModelProvider | None = None,
) -> FastAPI:
    """Create the local Studio FastAPI app."""

    resolved_static_dir = resolve_static_dir(static_dir)
    app = FastAPI(
        title="Hephaestus Studio",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_cors_origins(host=host, port=port),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.state.studio_service = StudioService(
        database_path,
        provider=provider,
        static_assets_available=resolved_static_dir is not None,
    )
    app.include_router(router, prefix="/api")
    if resolved_static_dir is not None:
        app.mount("/", StudioStaticFiles(directory=resolved_static_dir, html=True), name="studio")
    return app


def resolve_static_dir(static_dir: Path | str | None = None) -> Path | None:
    """Return the exported Studio frontend directory if it exists."""

    return resolve_static_assets_dir(__file__, static_dir)
