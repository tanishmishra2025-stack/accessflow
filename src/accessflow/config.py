import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://accessflow:accessflow@db:5432/accessflow"
)