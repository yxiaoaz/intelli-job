from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import auth, jobs, chat
from app.middleware.error_handler import register_exception_handlers
from app.utils.logger import setup_logging, get_logger
from app.config import get_settings

# Initialize settings and logging
settings = get_settings()
setup_logging()
logger = get_logger()

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered job matching platform with DeepAgents",
    version=settings.APP_VERSION,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["职位"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["AI对话"])


@app.get("/")
def read_root():
    """Root endpoint"""
    return {
        "message": "Welcome to Intelli-Job API",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
