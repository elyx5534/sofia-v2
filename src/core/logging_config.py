"""
Centralized logging configuration for Sofia V2
"""

import json
import logging
import logging.handlers
import time
from pathlib import Path

# Create logs directory
Path("logs").mkdir(exist_ok=True)


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record):
        log_obj = {
            "timestamp": int(time.time() * 1000),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "symbol"):
            log_obj["symbol"] = record.symbol
        if hasattr(record, "side"):
            log_obj["side"] = record.side
        if hasattr(record, "qty"):
            log_obj["qty"] = record.qty
        if hasattr(record, "price_used"):
            log_obj["price_used"] = record.price_used
        if hasattr(record, "price_source"):
            log_obj["price_source"] = record.price_source
        if hasattr(record, "ts_ms"):
            log_obj["ts_ms"] = record.ts_ms

        return json.dumps(log_obj)


def setup_logging():
    """Setup logging configuration for the entire project"""

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)

    # File handler for general logs
    file_handler = logging.handlers.RotatingFileHandler(
        "logs/sofia.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,  # 10MB
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(console_formatter)

    # Paper audit log handler with JSON formatter
    paper_audit_handler = logging.handlers.RotatingFileHandler(
        "logs/paper_audit.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,  # 10MB
    )
    paper_audit_handler.setLevel(logging.INFO)
    paper_audit_handler.setFormatter(JsonFormatter())

    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Paper trading logger
    paper_logger = logging.getLogger("paper_trading")
    paper_logger.addHandler(paper_audit_handler)
    paper_logger.setLevel(logging.INFO)

    return root_logger


# Initialize logging on import
logger = setup_logging()
