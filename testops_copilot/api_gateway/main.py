"""
API Gateway - главный файл FastAPI приложения
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn

from shared.config.settings import settings
from shared.utils.database import init_db
from shared.utils.logger import api_logger
from api_gateway.routers import generate, tasks, validate, optimize, health, stream, github, test_plan, integrations
try:
    from api_gateway.routers import metrics
except ImportError:
    metrics = None
from api_gateway.routers import gitlab as gitlab_router
from api_gateway.middleware.logging_middleware import LoggingMiddleware
import logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    # Startup
    api_logger.info("Starting API Gateway", extra={"host": settings.api_gateway_host, "port": settings.api_gateway_port})
    try:
        init_db()
        api_logger.info("Database initialized")
    except Exception as e:
        api_logger.error(f"Database initialization error: {e}", exc_info=True)
    yield
    # Shutdown
    api_logger.info("Shutting down API Gateway...")


app = FastAPI(
    title="TestOps Copilot API",
    description="AI QA Assistant для автоматической генерации тест-кейсов",
    version="1.0.0",
    lifespan=lifespan
)

# Logging middleware
app.add_middleware(LoggingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(generate.router, prefix="/api/v1", tags=["Generation"])
app.include_router(tasks.router, prefix="/api/v1", tags=["Tasks"])
app.include_router(stream.router, prefix="/api/v1", tags=["Streaming"])
app.include_router(validate.router, prefix="/api/v1", tags=["Validation"])
app.include_router(optimize.router, prefix="/api/v1", tags=["Optimization"])
app.include_router(gitlab_router.router, prefix="/api/v1", tags=["GitLab"])
app.include_router(github.router, prefix="/api/v1", tags=["GitHub"])
app.include_router(test_plan.router, prefix="/api/v1", tags=["Test Plan"])
app.include_router(integrations.router, prefix="/api/v1", tags=["Integrations"])
app.include_router(health.router, tags=["Health"])
if metrics:
    app.include_router(metrics.router, tags=["Metrics"])

# Статические файлы для frontend
try:
    import os
    static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.exists(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")
        # Главная страница
        @app.get("/")
        async def root():
            from fastapi.responses import FileResponse
            index_path = os.path.join(static_path, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return {"message": "TestOps Copilot API", "docs": "/docs"}
except Exception as e:
    api_logger.warning(f"Could not mount static files: {e}")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Глобальный обработчик ошибок"""
    import traceback
    error_trace = traceback.format_exc()
    api_logger.error(
        f"Global exception: {exc}",
        extra={
            "path": str(request.url),
            "method": request.method,
            "error_type": type(exc).__name__,
            "traceback": error_trace
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "request_id": getattr(request.state, "request_id", None),
            "type": type(exc).__name__
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_gateway_host,
        port=settings.api_gateway_port,
        reload=settings.api_gateway_reload
    )

