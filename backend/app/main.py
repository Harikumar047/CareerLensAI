import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from pydantic import BaseModel
from app.config import settings
from app.api import resume, jobs, matching, mentor, skills, courses
from app.services.resume_extractor import ResumeExtractorService
from app.services.job_parser import JobParserService
from app.services.embedding_service import EmbeddingService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload models on startup unless running in a test context
    if os.getenv("TESTING") != "1":
        import logging
        _log = logging.getLogger("app.main")
        for svc_name, loader in [
            ("ResumeExtractor", ResumeExtractorService().load_model),
            ("JobParser", JobParserService().load_model),
            ("EmbeddingService", EmbeddingService().load_model),
        ]:
            try:
                loader()
            except Exception as e:
                _log.warning(f"Failed to preload {svc_name} at startup: {e}")
    yield

from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for CareerLensAI - AI Career Mentor for Students",
    version="0.1.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint model
class HealthStatus(BaseModel):
    status: str
    app_name: str

@app.get("/health", response_model=HealthStatus, status_code=status.HTTP_200_OK)
async def health_check() -> HealthStatus:
    """
    Service health check endpoint.
    """
    return HealthStatus(
        status="healthy",
        app_name=settings.APP_NAME
    )

# Include API sub-routers
app.include_router(resume.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(matching.router, prefix="/api")
app.include_router(mentor.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(courses.router, prefix="/api")
