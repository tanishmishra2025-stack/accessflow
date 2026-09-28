from fastapi import FastAPI
from accessflow.config import DATABASE_URL
from accessflow.routers.audits import router as audits_router

app = FastAPI(
    title="AccessFlow API",
    description="Automated web accessibility audit API",
    version="0.1.0"
)

app.include_router(audits_router)

@app.get("/")
def root():
    return {
        "message": "AccessFlow API — see /docs for the interactive API explorer"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "accessflow",
        "database_url_configured": bool(DATABASE_URL)
    }