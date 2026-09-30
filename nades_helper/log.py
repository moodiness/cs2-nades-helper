from __future__ import annotations

import logging
import sys

PACKAGE_LOGGER = "nades_helper"


def configure_logging(*, verbose: bool = False, quiet: bool = False) -> None:
    """Log to stderr: INFO by default, DEBUG with ``verbose``, WARNING+ with ``quiet``."""
    level = logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO
    fmt = "%(asctime)s %(levelname)-7s %(message)s"
    if verbose:
        fmt = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    logger = logging.getLogger(PACKAGE_LOGGER)
    logger.handlers[:] = [handler]
    logger.setLevel(level)
    logger.propagate = False
