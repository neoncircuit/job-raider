# Job Raider - Streamlit Dashboard Dockerfile
#
# Lightweight Python image for the web dashboard.
# Connects to the backend API via Docker internal networking.
#
# Usage:
#   docker build -t job-raider-frontend -f frontend-py/docker/Dockerfile frontend-py/
#   docker run -e BACKEND_API_URL=http://backend:8000 -p 8501:8501 job-raider-frontend

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ ./config/
COPY src/ ./src/
COPY main.py .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
