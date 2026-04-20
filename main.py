import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import check_database_health
from api.auth import get_current_user
from api.chat import router as chat_router
from api.me import router as me_router

# Configure logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Verify services
    logger.info("Starting up BodhCS API...")
    health = await check_database_health()
    logger.info(f"Service health status: {health}")
    
    # Check if critical services are up (optional: fail startup if not)
    # if health["supabase"] == "down":
    #     logger.error("Supabase is unreachable!")
        
    yield
    # Shutdown logic if any
    logger.info("Shutting down BodhCS API...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Cognitive Tutor Backend for CS Subjects",
    version="0.1.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your Flutter app's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Welcome to BodhCS API",
        "status": "online",
        "version": "0.1.0"
    }

@app.get("/health")
async def health_check():
    health = await check_database_health()
    if any(status == "down" for status in health.values()):
        # Return 503 if any dependency is down
        raise HTTPException(status_code=503, detail=health)
    return {
        "status": "healthy",
        "services": health
    }

@app.get("/api/v1/protected", dependencies=[Depends(get_current_user)])
async def protected_route():
    return {"message": "You have access to this protected resource."}

# Register Routers
app.include_router(chat_router)
app.include_router(me_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
