from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, initialize_database
from .routers.interviews import router
from .routers.interview_session import router as session_router
from .routers.transcription import router as transcription_router
from .routers.integrity import router as integrity_router
from .routers.reports import router as reports_router

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def create_app(database_engine=engine):
    @asynccontextmanager
    async def lifespan(app):
        initialize_database(database_engine)
        yield

    application = FastAPI(title="Interview Bot — Phase 5", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        # Live Server may choose another port when its default port is occupied.
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):[0-9]+",
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )
    application.include_router(router)
    application.include_router(session_router)
    application.include_router(transcription_router)
    application.include_router(integrity_router)
    application.include_router(reports_router)

    @application.get("/health")
    def health():
        return {"status": "ok"}

    return application


app = create_app()
