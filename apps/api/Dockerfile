FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --no-cache-dir .

CMD ["python", "-m", "app.workers.document_worker"]
