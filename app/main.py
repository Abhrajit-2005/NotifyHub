from fastapi import FastAPI
from app.core.config import settings
from app.api.v1 import auth, health, notifications

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Root health endpoint (GET /health)
@app.get("/health", status_code=200, tags=["Health"])
def root_health_check():
    return {"status": "ok"}

# Mount versioned v1 routers (/api/v1/health, /api/v1/auth, /api/v1/notifications)
app.include_router(health.router, prefix=settings.API_V1_STR, tags=["Health"])
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(notifications.router, prefix=settings.API_V1_STR)

