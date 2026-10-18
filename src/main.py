from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy import text

from src.config import settings
from src.infrastructure.database import init_db, get_db_engine
from src.infrastructure.redis_client import init_redis, get_redis_client
from src.infrastructure.temporal_client import init_temporal_client
from src.infrastructure.kafka_client import init_kafka


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Multi-Agent AI Platform...")
    await init_db()
    await init_redis()
    await init_temporal_client()
    # Kafka is observability-only — API stays up if it's unreachable
    try:
        await init_kafka()
    except Exception as e:
        print(f"⚠️ Kafka unavailable, events will not publish: {e}")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
async def health_check():
    """System health check endpoint (database, Redis, Temporal, Kafka)."""
    try:
        # Check database
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    try:
        # Check Redis
        if get_redis_client().ping():
            redis_status = "healthy"
        else:
            redis_status = "unhealthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    try:
        # Check Temporal (client is created at startup; verify connectivity)
        from src.infrastructure.temporal_client import get_temporal_client

        # The client only exists if Client.connect() succeeded at startup
        client = get_temporal_client()
        temporal_status = "healthy" if client else "unhealthy"
    except Exception as e:
        temporal_status = f"unhealthy: {str(e)}"

    try:
        # Check Kafka (producer initialized at startup)
        from src.infrastructure import kafka_client

        kafka_status = "healthy" if kafka_client.producer is not None else "unavailable"
    except Exception as e:
        kafka_status = f"unhealthy: {str(e)}"

    core_healthy = db_status == "healthy" and redis_status == "healthy" and temporal_status == "healthy"
    return JSONResponse(
        status_code=200,
        content={
            "status": "operational" if core_healthy else "degraded",
            "services": {
                "database": db_status,
                "redis": redis_status,
                "temporal": temporal_status,
                "kafka": kafka_status,
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
from src.routes.approvals import router as approvals_router
from src.routes.memory import router as memory_router
from src.routes.observability import router as observability_router
from src.routes.rate_limiting import router as rate_limiting_router
from src.routes.prompts import router as prompts_router
from src.routes.skills import router as skills_router

app.include_router(workflows_router)
app.include_router(tools_router)
app.include_router(approvals_router)
app.include_router(memory_router)
app.include_router(observability_router)
app.include_router(rate_limiting_router)
app.include_router(prompts_router)
app.include_router(skills_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_ENVIRONMENT == "development",
        log_level=settings.API_LOG_LEVEL.lower(),
    )
