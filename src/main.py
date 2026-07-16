from fastapi import FastAPI
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from src.config import settings
from src.infrastructure.database import init_db, get_db_engine
from src.infrastructure.redis_client import init_redis, redis_client
from src.infrastructure.temporal_client import init_temporal_client


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Multi-Agent AI Platform...")
    await init_db()
    await init_redis()
    await init_temporal_client()
    print("✅ All services initialized")

    yield

    # Shutdown
    print("🛑 Shutting down...")
    # Cleanup if needed
    print("✅ Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade multi-agent AI orchestration platform",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["System"])
async def health_check():
    """System health check endpoint."""
    try:
        # Check database
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    try:
        # Check Redis
        if redis_client and redis_client.ping():
            redis_status = "healthy"
        else:
            redis_status = "unhealthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    return JSONResponse(
        status_code=200,
        content={
            "status": "operational" if db_status == "healthy" and redis_status == "healthy" else "degraded",
            "services": {
                "database": db_status,
                "redis": redis_status,
            },
            "environment": settings.API_ENVIRONMENT,
        }
    )


@app.get("/", tags=["System"])
async def root():
    """API root endpoint."""
    return {
        "message": "Multi-Agent AI Platform API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# Route imports
from src.routes.workflows import router as workflows_router
from src.routes.tools import router as tools_router

app.include_router(workflows_router)
app.include_router(tools_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_ENVIRONMENT == "development",
        log_level=settings.API_LOG_LEVEL.lower(),
    )
