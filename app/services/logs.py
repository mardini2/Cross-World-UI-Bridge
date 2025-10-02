"""
Goal: Set up loguru logging to a rolling log file under %LOCALAPPDATA%/UIBridge/logs.
Keep output friendly and avoid leaking secrets.
"""

from pathlib import Path

from loguru import logger

from app.settings import LOG_DIR


def _sanitize_log_message(msg: str) -> str:
    """Remove sensitive information from log messages."""
    import re
    
    # Remove tokens (anything that looks like a token)
    msg = re.sub(r'[A-Za-z0-9_-]{20,}', '[REDACTED]', msg)
    
    # Remove potential passwords/secrets
    msg = re.sub(r'(password|secret|key|token)[\s=:]+[^\s]+', r'\1=[REDACTED]', msg, flags=re.IGNORECASE)
    
    return msg


def _filter_sensitive_logs(record):
    """Filter out sensitive log records."""
    message = record["message"].lower()
    
    # Don't log messages containing sensitive keywords
    sensitive_keywords = ['token', 'password', 'secret', 'key']
    if any(keyword in message for keyword in sensitive_keywords):
        return False
    
    return True


def configure_logging() -> None:
    logger.remove()
    logger.add(
        lambda msg: print(_sanitize_log_message(msg), end=""), 
        colorize=True, 
        backtrace=False, 
        diagnose=False
    )
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
        filter=_filter_sensitive_logs,
    )
