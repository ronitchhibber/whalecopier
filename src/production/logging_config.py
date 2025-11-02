"""
Production Logging Configuration - Comprehensive logging for production deployment.

Features:
- Structured logging (JSON format)
- Log rotation and archiving
- Multiple log levels and handlers
- Trade audit logging
- Error tracking with stack traces
- Performance metrics logging
- Integration with external logging services (optional)
"""

import logging
import logging.handlers
import json
import traceback
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path
from decimal import Decimal


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""

        log_data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }

        # Add extra fields
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra

        return json.dumps(log_data)


class TradeAuditLogger:
    """Separate logger for trade audit trail"""

    def __init__(self, log_file: str = "logs/trade_audit.log"):
        self.logger = logging.getLogger("trade_audit")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  # Don't propagate to root logger

        # Ensure log directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # Rotating file handler (100MB, keep 10 files)
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )

        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)

    def log_trade_opened(self, trade_data: Dict):
        """Log when a trade is opened"""
        self.logger.info("TRADE_OPENED", extra={
            "event": "trade_opened",
            "trade_id": trade_data.get("trade_id"),
            "whale_address": trade_data.get("whale_address"),
            "market_id": trade_data.get("market_id"),
            "side": trade_data.get("side"),
            "size": str(trade_data.get("size")),
            "price": str(trade_data.get("price")),
            "timestamp": trade_data.get("timestamp")
        })

    def log_trade_closed(self, trade_data: Dict):
        """Log when a trade is closed"""
        self.logger.info("TRADE_CLOSED", extra={
            "event": "trade_closed",
            "trade_id": trade_data.get("trade_id"),
            "pnl_usd": str(trade_data.get("pnl_usd")),
            "exit_price": str(trade_data.get("exit_price")),
            "hold_time_seconds": trade_data.get("hold_time_seconds"),
            "timestamp": trade_data.get("timestamp")
        })

    def log_risk_event(self, event_data: Dict):
        """Log risk management events"""
        self.logger.warning("RISK_EVENT", extra={
            "event": "risk_event",
            "event_type": event_data.get("event_type"),
            "risk_level": event_data.get("risk_level"),
            "message": event_data.get("message"),
            "action_taken": event_data.get("action_taken"),
            "timestamp": event_data.get("timestamp")
        })


class PerformanceLogger:
    """Logger for performance metrics"""

    def __init__(self, log_file: str = "logs/performance.log"):
        self.logger = logging.getLogger("performance")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # Ensure log directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # Rotating file handler
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=50 * 1024 * 1024,
            backupCount=5
        )

        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)

    def log_operation(self, operation: str, duration_ms: float, **kwargs):
        """Log performance of an operation"""
        self.logger.info(f"OPERATION: {operation}", extra={
            "operation": operation,
            "duration_ms": duration_ms,
            **kwargs
        })

    def log_api_call(self, endpoint: str, duration_ms: float, status_code: int):
        """Log external API call performance"""
        self.logger.info(f"API_CALL: {endpoint}", extra={
            "endpoint": endpoint,
            "duration_ms": duration_ms,
            "status_code": status_code
        })


def setup_production_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    enable_console: bool = True,
    enable_json: bool = True
):
    """
    Setup production logging configuration.

    Creates multiple log files:
    - main.log: General application logs
    - error.log: Error and critical logs only
    - trade_audit.log: Trade audit trail
    - performance.log: Performance metrics
    """

    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        if enable_json:
            console_handler.setFormatter(JSONFormatter())
        else:
            console_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_format)

        root_logger.addHandler(console_handler)

    # Main log file (all logs)
    main_handler = logging.handlers.RotatingFileHandler(
        log_path / "main.log",
        maxBytes=100 * 1024 * 1024,  # 100MB
        backupCount=10
    )
    main_handler.setLevel(logging.DEBUG)

    if enable_json:
        main_handler.setFormatter(JSONFormatter())
    else:
        main_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

    root_logger.addHandler(main_handler)

    # Error log file (errors and critical only)
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "error.log",
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=10
    )
    error_handler.setLevel(logging.ERROR)

    if enable_json:
        error_handler.setFormatter(JSONFormatter())
    else:
        error_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s'
        ))

    root_logger.addHandler(error_handler)

    # Initialize specialized loggers
    trade_audit = TradeAuditLogger(str(log_path / "trade_audit.log"))
    performance = PerformanceLogger(str(log_path / "performance.log"))

    logging.info(f"Production logging initialized - Log directory: {log_path}")
    logging.info(f"Log level: {log_level}")
    logging.info(f"JSON format: {enable_json}")

    return {
        "trade_audit": trade_audit,
        "performance": performance
    }


# Context manager for timing operations

class timed_operation:
    """Context manager for timing and logging operations"""

    def __init__(self, operation_name: str, logger: Optional[PerformanceLogger] = None):
        self.operation_name = operation_name
        self.logger = logger or PerformanceLogger()
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.utcnow() - self.start_time).total_seconds() * 1000
        self.logger.log_operation(
            self.operation_name,
            duration,
            success=(exc_type is None)
        )

        # Don't suppress exceptions
        return False


# Example usage

if __name__ == "__main__":
    # Setup logging
    loggers = setup_production_logging(
        log_dir="logs",
        log_level="INFO",
        enable_console=True,
        enable_json=True
    )

    # Test logging
    logging.info("Application started")
    logging.warning("This is a warning")
    logging.error("This is an error")

    try:
        raise ValueError("Test exception")
    except Exception as e:
        logging.exception("Exception occurred")

    # Test trade audit
    loggers["trade_audit"].log_trade_opened({
        "trade_id": "trade_123",
        "whale_address": "0x1234",
        "market_id": "market_456",
        "side": "BUY",
        "size": Decimal("100"),
        "price": Decimal("0.52"),
        "timestamp": datetime.utcnow().isoformat()
    })

    # Test performance logging
    with timed_operation("test_operation", loggers["performance"]):
        import time
        time.sleep(0.1)

    logging.info("Logging test complete")
