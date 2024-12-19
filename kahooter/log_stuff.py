import logging


def create_colored_logger(
    name: str,
    level: int,
) -> logging.Logger:
    manager_logger = logging.getLogger(name)

    manager_handler = ColoredStreamHandler()
    manager_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
    )
    manager_logger.addHandler(manager_handler)
    manager_logger.setLevel(level)

    return manager_logger


class ColoredStreamHandler(logging.StreamHandler):
    COLORS = {
        logging.DEBUG: "\x1b[34;1m",  # blue
        logging.INFO: "\x1b[32;1m",  # green
        logging.WARNING: "\x1b[33;1m",  # yellow
        logging.ERROR: "\x1b[31;1m",  # red
        logging.CRITICAL: "\x1b[31;47;1m",  # red + white background
    }

    RESET_COLOR = "\x1b[0m"

    def format_message(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.COLORS[logging.INFO])

        message = self.format(record)

        return f"{color}{message}{self.RESET_COLOR}"

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format_message(record)
            stream = self.stream
            stream.write(msg + "\n")
            stream.flush()
        except Exception:
            self.handleError(record)
