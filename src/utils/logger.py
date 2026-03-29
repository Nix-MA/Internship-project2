import logging
import logging.handlers
import os
from pathlib import Path

# Ensure logs directory exists
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Formatters
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# App file handler (rotating)
app_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "app.log", maxBytes=5 * 1024 * 1024, backupCount=2
)
app_handler.setLevel(logging.INFO)
app_handler.setFormatter(formatter)

# Error file handler (rotating)
error_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "error.log", maxBytes=5 * 1024 * 1024, backupCount=2
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

def get_logger(name: str) -> logging.Logger:
    """Get a strictly structured logger instance."""
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if get_logger is called multiple times
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logger.addHandler(app_handler)
        logger.addHandler(error_handler)
        logger.addHandler(console_handler)
    
    return logger
