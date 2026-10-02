FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=3000

COPY app_server.py ./app_server.py
COPY public/ ./public/

EXPOSE 3000
CMD ["python3", "app_server.py"]
