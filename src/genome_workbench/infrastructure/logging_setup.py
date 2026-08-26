from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from genome_workbench.infrastructure.filesystem.paths import logs_dir

_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger("genome_workbench")
    if _CONFIGURED:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = RotatingFileHandler(
        logs_dir() / "genome_workbench.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _CONFIGURED = True
    return logger
