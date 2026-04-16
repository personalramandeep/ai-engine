import logging
import sys
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

RESET  = "\033[0m"
BOLD   = "\033[1m"

COLORS = {
    "DEBUG":    "\033[36m",   # cyan
    "INFO":     "\033[32m",   # green
    "WARNING":  "\033[33m",   # yellow
    "ERROR":    "\033[31m",   # red
    "CRITICAL": "\033[41m",   # red background
}

NAME_COLOR  = "\033[35m"   # magenta for logger name
TIME_COLOR  = "\033[90m"   # dark grey for timestamp


class ColorFormatter(logging.Formatter):
    def format(self, record):
        level_color = COLORS.get(record.levelname, RESET)
        record.levelname = f"{level_color}{BOLD}{record.levelname:<8}{RESET}"
        record.name      = f"{NAME_COLOR}{record.name}{RESET}"
        record.asctime   = f"{TIME_COLOR}{self.formatTime(record, self.datefmt)}{RESET}"
        record.msg       = f"{level_color}{record.getMessage()}{RESET}"
        record.args      = None  # already formatted above
        return f"{record.asctime} [{record.levelname}] [{record.name}] {record.msg}"


class PlainFormatter(logging.Formatter):
    """Plain formatter for file logs — no ANSI codes."""
    pass


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Colored console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(ColorFormatter(datefmt="%Y-%m-%d %H:%M:%S"))

    # Plain file handler
    file_handler = logging.FileHandler(LOG_DIR / "kreeda.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(PlainFormatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger
