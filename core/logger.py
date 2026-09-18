"""Logging configuration shared by the application."""
import logging
import sys
from config import get_settings

def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.DEBUG if settings.debug else getattr(logging, settings.log_level, logging.INFO), format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", stream=sys.stdout)

def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
