
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/")
def home():
    return {
        "message": "Welcome to CyberGuard",
        "docs": "/docs",
        "health": "/api/health"
    }


app.mount("/", a2a_app)
