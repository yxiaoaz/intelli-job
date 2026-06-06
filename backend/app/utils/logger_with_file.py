import structlog
import logging
import sys
from pathlib import Path


def setup_logging(log_to_file: bool = False, log_dir: str = "logs"):
    """Configure structured logging
    
    Args:
        log_to_file: Whether to save logs to file (default: False)
        log_dir: Directory to store log files (default: "logs")
    """
    
    # Create log directory if needed
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
    
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
    ]
    
    if log_to_file:
        # For file output, use JSON format for better parsing
        processors.append(structlog.processors.JSONRenderer())
        
        # Configure file handler
        log_file = Path(log_dir) / "app.log"
        
        # Create a standard Python logger with file handler
        python_logger = logging.getLogger()
        python_logger.setLevel(logging.INFO)
        
        # File handler (JSON format)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Console handler (human-readable format)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        python_logger.addHandler(file_handler)
        python_logger.addHandler(console_handler)
        
        # Configure structlog to use the Python logger
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger("INFO"),
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=False,
        )
    else:
        # For console output, use human-readable format
        processors.append(structlog.dev.ConsoleRenderer())
        
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger("INFO"),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )


def get_logger():
    """Get a structured logger instance"""
    return structlog.get_logger()
