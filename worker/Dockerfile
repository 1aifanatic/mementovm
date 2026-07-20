FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY backend ./backend
COPY worker ./worker
RUN pip install --no-cache-dir .
CMD ["python", "-m", "worker.run"]

