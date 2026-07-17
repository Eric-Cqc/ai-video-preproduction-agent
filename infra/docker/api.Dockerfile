FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir alembic fastapi jsonschema pydantic pydantic-settings 'psycopg[binary]' sqlalchemy uvicorn
COPY services ./services
COPY packages ./packages
COPY infra ./infra
CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
