import structlog
import sys

def setup_logging():
    """Configure structured logging"""
    
    # Detect if running on Windows and enable ANSI support
    if sys.platform == "win32":
        try:
            import colorama
            colorama.init()
        except ImportError:
            # If colorama not installed, structlog will still work but without colors
            pass
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger("INFO"),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger():
    """Get a structured logger instance"""
    return structlog.get_logger()
