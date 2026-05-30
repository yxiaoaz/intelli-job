from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.utils.logger import get_logger

logger = get_logger()


class APIError(Exception):
    """Custom API error"""
    def __init__(self, status_code: int, error_code: str, message: str, details: dict = None):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or {}


def register_exception_handlers(app: FastAPI):
    """Register global exception handlers"""
    
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        logger.error(
            "api_error",
            path=request.url.path,
            error_code=exc.error_code,
            message=exc.message
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            error=str(exc),
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {}
                }
            }
        )
