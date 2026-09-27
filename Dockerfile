FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN pip install uv

COPY src ./src

RUN uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "accessflow.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]