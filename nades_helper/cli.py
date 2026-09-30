from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from nades_helper import __version__
from nades_helper.build import run_build
from nades_helper.errors import NadesHelperError
from nades_helper.exporters import EXPORTERS
from nades_helper.log import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_INPUT_DIR = Path("nades")
DEFAULT_OUTPUT_DIR = Path("out")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nades-helper",
        description="Convert CS2 grenade annotation files (KV3) into grenade-helper JSON.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    common = argparse.ArgumentParser(add_help=False)
    verbosity = common.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="show debug details")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="only show warnings/errors")

    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    build = commands.add_parser(
        "build", parents=[common], help="generate JSON files from the nades folder"
    )
    build.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="folder containing the annotation sub-folders (default: %(default)s)",
    )
    build.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="folder receiving one sub-folder per format (default: %(default)s)",
    )
    build.add_argument(
        "--format",
        dest="formats",
        action="append",
        choices=list(EXPORTERS),
        help="format to generate, repeatable (default: all)",
    )
    build.set_defaults(handler=_build)

    return parser


def _build(args: argparse.Namespace) -> None:
    formats = list(dict.fromkeys(args.formats or EXPORTERS))
    run_build(args.input_dir, args.output_dir, formats)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose, quiet=args.quiet)

    try:
        args.handler(args)
    except NadesHelperError as exc:
        LOGGER.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        LOGGER.error("Interrupted")
        return 130
    except Exception:
        LOGGER.exception("Unexpected error")
        return 1

    return 0
