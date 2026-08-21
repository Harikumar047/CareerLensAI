# Use standard lightweight Python 3.10 image
FROM python:3.10-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Set up user for Hugging Face Spaces (user ID 1000)
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# Install system dependencies (build-essential, curl if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY --chown=user:user ./requirements.txt /home/user/app/requirements.txt

# Install Python dependencies (using CPU-only torch to save download time and disk space)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=user:user ./app /home/user/app/app

# Switch to non-root user
USER user

# Expose Hugging Face default port
EXPOSE 7860

# Start FastAPI server via Uvicorn on port 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
