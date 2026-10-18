"""Creates the FastAPI application.

Run locally:   uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_compare, routes_runs, routes_scenarios
from app.api.errors import register_error_handlers
from app.config import Settings, get_settings
from app.storage.database import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # create_all only creates missing tables. A real project with a
        # changing schema would use migrations (Alembic) instead.
        database.create_tables()
        yield

    app = FastAPI(title="ReplayLab Collector", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.database = database

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        length = request.headers.get("content-length")
        if length is not None and length.isdigit() and int(length) > settings.max_request_bytes:
            return JSONResponse(
                status_code=413,
                content={"error": {"code": "payload_too_large", "message": f"request body is larger than {settings.max_request_bytes} bytes", "details": None}},
            )
        return await call_next(request)

    register_error_handlers(app)
    app.include_router(routes_runs.router)
    app.include_router(routes_compare.router)
    app.include_router(routes_scenarios.router)

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
