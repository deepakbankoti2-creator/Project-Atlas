"""
Project Atlas — AI Software Developer / Report Copilot
Main FastAPI Application Entrypoint

Features:
- Request ID tracing and latency tracking middleware
- Safe structured logging without secret or confidential data leaks
- Pre-retrieval entitlement filtering on /chat
- Protected administrative endpoints (/ingest, /escalations) with API key authentication
- Multi-dependency health monitoring (/health)
"""

import time
import uuid
import logging
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.api.v1.endpoints import router as api_router
from backend.app.core.config import settings

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("atlas.api")


# ---------------------------------------------------------------------------
# Middleware: Request Tracing & Structured Latency Monitoring
# ---------------------------------------------------------------------------

class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Assigns or preserves unique X-Request-ID for every HTTP transaction.
    Measures end-to-end latency and attaches performance headers.
    Logs structured audit lines without exposing secrets or document bodies.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id
        start_time = time.perf_counter()

        client_host = request.client.host if request.client else "unknown"
        logger.info(f"[{req_id}] INCOMING {request.method} {request.url.path} (from {client_host})")

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
            logger.info(f"[{req_id}] COMPLETED {request.method} {request.url.path} -> {response.status_code} ({duration_ms:.2f}ms)")
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"[{req_id}] FAILED {request.method} {request.url.path}: {exc} ({duration_ms:.2f}ms)")
            raise


# ---------------------------------------------------------------------------
# FastAPI Application Initialization
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Project Atlas API",
    description="Enterprise Syndicated Market Research Report Copilot & AI Agent Backend",
    version="1.0.0"
)

# 1. Attach Request Context Middleware
app.add_middleware(RequestContextMiddleware)

# 2. CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Mount Routes (both under /api/v1 and at root for full endpoint flexibility)
app.include_router(api_router, prefix="/api/v1", tags=["API v1"])
app.include_router(api_router, tags=["Root Endpoints"])


@app.get("/", tags=["Info"])
def root():
    return {
        "project": "Project Atlas — AI Software Developer / Report Copilot",
        "version": "1.0.0",
        "status": "operational",
        "docs_url": "/docs",
        "endpoints": {
            "health": "/health",
            "chat": "/chat",
            "ingest": "/ingest",
            "escalations": "/escalations"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
