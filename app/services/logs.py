"""
Goal: Set up loguru logging to a rolling log file under %LOCALAPPDATA%/UIBridge/logs.
Keep output friendly and avoid leaking secrets.
"""
from loguru import logger
from . import __init__  # quiet lint
from app.settings import LOG_DIR
from pathlib import Path

def configure_logging() -> None:
    # Remove default sinks to control format
    logger.remove()
    # Log to console (dev convenience)
    logger.add(lambda msg: print(msg, end=""), colorize=True, backtrace=False, diagnose=False)
    # Log to daily-rotated file
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(Path(LOG_DIR) / "{time:YYYY-MM-DD}.log"),
        rotation="00:00",
        retention="14 days",
        level="INFO",
        backtrace=False,
        diagnose=False,
        serialize=False,
        enqueue=True,
    )
