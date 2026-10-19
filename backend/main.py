from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.v1.endpoints import router as api_router
from backend.app.core.config import settings

app = FastAPI(
    title="Project Atlas API",
    description="AI Software Developer / Report Copilot Backend",
    version="1.0.0"
)

# CORS configuration for future frontend connectivity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "project": "Project Atlas — AI Software Developer / Report Copilot",
        "version": "1.0.0",
        "status": "operational",
        "docs_url": "/docs"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "database_target": settings.DB_NAME,
        "host": settings.DB_HOST
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
