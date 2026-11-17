
import os

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config.settings import APP_NAME
from backend.app.api.routes import router
from backend.app.a2a.server import app as a2a_app

app = FastAPI(
    title=APP_NAME,
    description="Agentic AI for cybersecurity incident investigation",
    version="0.1.0"
)

# Comma-separated list. In production nginx serves the UI and API from one
# origin, so CORS is only needed for the Vite dev server.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(router, prefix="/api")


# Optionally serve the built React UI from this same process (used by the
# single-container Hugging Face Space). Locally, Vite serves the UI instead.
FRONTEND_DIST = Path(
    os.getenv(
        "FRONTEND_DIST",
        Path(__file__).resolve().parents[2] / "frontend" / "dist",
    )
)
SERVE_FRONTEND = (
    os.getenv("SERVE_FRONTEND", "0").strip().lower() in {"1", "true", "yes"}
    and (FRONTEND_DIST / "index.html").is_file()
)

if SERVE_FRONTEND:
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="frontend-assets",
    )

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        return FileResponse(FRONTEND_DIST / "favicon.svg")

    @app.get("/icons.svg", include_in_schema=False)
    def icons():
        return FileResponse(FRONTEND_DIST / "icons.svg")


@app.get("/")
def home():
    if SERVE_FRONTEND:
        return FileResponse(FRONTEND_DIST / "index.html")

    return {
        "message": "Welcome to CyberGuard",
        "docs": "/docs",
        "health": "/api/health"
    }


app.mount("/", a2a_app)
