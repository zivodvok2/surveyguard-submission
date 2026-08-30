import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import shared_db
from routers import agentic, ai, auth, compare, dashboard, interviewers, projects, qc

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    shared_db.init_tables()
    yield


app = FastAPI(
    title="SurveyGuard API",
    description="Deterministic and agentic multimodal quality control for survey research.",
    version="3.0.0",
    lifespan=lifespan,
)

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _raw_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(qc.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(interviewers.router, prefix="/api")
app.include_router(agentic.router, prefix="/api")


@app.get("/health")
async def health():
    try:
        version = json.loads(Path("assets/app_version.json").read_text())["version"]
    except Exception:
        version = "unknown"
    return {"status": "ok", "version": version}


# Serve the React frontend (datasense-ui/dist) at the root.
# This makes http://10.x.x.x:8000 open the app directly — no separate
# dev server or VITE_DASHBOARD_API_URL config needed on LAN.
_dist = Path(__file__).parent / "datasense-ui" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file = _dist / full_path
        if file.exists() and file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(_dist / "index.html"))
