# logger.py


class AppLogger:
    """A simple logger class to handle different log levels."""

    def __init__(self, log_callback, level="Normal"):
        self.log_callback = log_callback
        self.level = level

    def info(self, message):
        """Logs a standard informational message."""
        self.log_callback(message)

    def debug(self, message):
        """Logs a message only if the log level is set to 'Debug'."""
        if self.level == "Debug":
            self.log_callback(f"[DEBUG] {message}")

    def error(self, message):
        """Logs an error message."""
        self.log_callback(f"[ERROR] {message}")

    def fatal(self, message):
        """Logs a fatal error message with distinctive formatting."""
        self.log_callback(f"\n--- [FATAL] {message} ---")
