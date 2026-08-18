import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    """
    APP_NAME: str = "CareerLensAI Backend"
    DEBUG: bool = False
    
    # Adzuna API Configuration
    ADZUNA_APP_ID: str = Field(default="", description="Adzuna API application ID")
    ADZUNA_APP_KEY: str = Field(default="", description="Adzuna API application key")
    ADZUNA_COUNTRY: str = Field(default="in", description="Adzuna API country code")

    # YouTube API Configuration
    YOUTUBE_API_KEY: str = Field(default="", description="YouTube Data API key")
    YOUTUBE_CACHE_TTL_SECONDS: int = Field(default=3600, description="Cache TTL in seconds for dynamic learning resources")

    # Base & Storage Directories
    BASE_DIR: Path = Path(__file__).resolve().parent
    DATA_DIR: Path = BASE_DIR / "data"
    RESUMES_DIR: Path = DATA_DIR / "resumes"
    JOBS_DIR: Path = DATA_DIR / "jobs"
    COURSES_DIR: Path = DATA_DIR / "courses"

    # Configure Pydantic to read environment files
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def create_dirs(self) -> None:
        """
        Creates storage directories if they do not exist.
        """
        self.RESUMES_DIR.mkdir(parents=True, exist_ok=True)
        self.JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self.COURSES_DIR.mkdir(parents=True, exist_ok=True)

# Initialize settings
settings = Settings()
settings.create_dirs()
