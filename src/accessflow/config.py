import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://accessflow:accessflow@db:5432/accessflow"
)