"""Logging utilities for MultiDisplay."""

import logging
from typing import Optional


def setup_logger(
    name: str = "multidisplay",
    level: int = logging.INFO,
    verbose: bool = False
) -> logging.Logger:
    """Configure and return a logger instance."""
    
    if verbose:
        level = logging.DEBUG
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def get_logger(name: str = "multidisplay") -> logging.Logger:
    """Get a logger instance by name."""
    return logging.getLogger(name)
