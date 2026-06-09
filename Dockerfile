FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY council/ council/

RUN pip install --no-cache-dir .

CMD ["python", "-m", "council.run"]
