"""
Logging Configuration.
Replicates Winston logger configuration with console and separate file output channels.
"""

import os
import logging
from logging.handlers import RotatingFileHandler

# Define logs directory in workspace
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Formatters
console_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] (%(name)s): %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_formatter = logging.Formatter(
    fmt='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S"
)

def _setup_logger(name: str, file_name: str, level: int = logging.INFO) -> logging.Logger:
    """Setup a logger with console and rolling file handlers."""
    logger_instance = logging.getLogger(name)
    logger_instance.setLevel(level)
    logger_instance.propagate = False # Avoid duplicate logging to root
    
    # Avoid adding duplicate handlers if already initialized
    if not logger_instance.handlers:
        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        logger_instance.addHandler(console_handler)
        
        # Rotating File Handler
        file_path = os.path.join(LOGS_DIR, file_name)
        file_handler = RotatingFileHandler(file_path, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        logger_instance.addHandler(file_handler)
        
    return logger_instance

# Global Logger Instances
logger = _setup_logger("api.app", "app.log")
request_logger = _setup_logger("api.requests", "requests.log")
audit_logger = _setup_logger("api.audit", "audit.log")
