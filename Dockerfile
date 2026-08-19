# Lightweight image for Hugging Face Spaces (SDK: docker), Zeabur, Fly.io,
# Koyeb, or any container host.
#
# Hugging Face Spaces expects the app on port 7860 and runs the container as
# UID 1000, so both are set explicitly below.

FROM python:3.12-slim

# Faster, quieter, no .pyc clutter in the image.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Hugging Face Spaces runs as this user; creating it keeps file permissions
# valid there and is harmless on other platforms.
RUN useradd -m -u 1000 appuser
USER appuser
ENV PATH="/home/appuser/.local/bin:$PATH"
WORKDIR /home/appuser/app

# Copy requirements first so dependency layers are cached across code edits.
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

# Spaces defaults to 7860; other platforms inject their own PORT.
ENV PORT=7860
EXPOSE 7860

# Shell form so ${PORT} is expanded at runtime rather than baked in.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
