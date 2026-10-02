FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=3000

COPY requirements.txt ./requirements.txt
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY app_server.py ./app_server.py
COPY aster/ ./aster/
COPY migrations/ ./migrations/
COPY scripts/ ./scripts/
COPY public/ ./public/

EXPOSE 3000
CMD ["sh", "-c", "uvicorn app_server:app --host 0.0.0.0 --port ${PORT:-3000} --no-access-log"]
