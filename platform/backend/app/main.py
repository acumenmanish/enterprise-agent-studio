from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health as health_route
from app.api.routes import studio as studio_route
from app.core.config import Settings, get_settings
from app.core.logging_config import configure_logging
from app.db.session import create_engine_for, create_session_factory, init_db
from app.services.seed import seed_local_demo


def create_app(settings: Settings | None = None, database_url: str | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.app_env)
    engine = create_engine_for(database_url or app_settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        with session_factory() as session:
            seed_local_demo(session, app_settings)
        yield
        engine.dispose()

    app = FastAPI(
        title="Enterprise Agent Studio",
        version="0.3.0-local",
        description="Local, manifest-driven production scheduling MVP",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "X-Tenant-ID"],
    )
    app.include_router(health_route.router)
    app.include_router(studio_route.router)
    return app


app = create_app()
