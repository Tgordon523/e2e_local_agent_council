FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY council/ council/

RUN pip install --no-cache-dir .

CMD ["python", "-m", "council.run"]
