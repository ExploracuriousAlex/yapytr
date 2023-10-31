"""
Module providing some helper functions for yapytr.
"""

import json
import logging
import re
from importlib.metadata import version

import coloredlogs
import requests
from packaging.version import parse as parse_version

log_level = None  # pylint: disable=invalid-name


def get_colored_logger(name=__name__, verbosity=None):
    """
    Return a logger with the specified name, creating it if necessary.
    If no name is specified, return the root logger.
    Enable colored terminal output.

    Args:
        name: Logger name. Defaults to __name__.
        verbosity: Logging level. Defaults to None.

    Returns:
        Logger
    """

    global log_level  # pylint: disable=global-statement

    if verbosity is not None:
        if log_level is None:
            log_level = verbosity
        else:
            raise RuntimeError("Verbosity has already been set.")

    shortname = name.replace("yapytr.", "")

    logger = logging.getLogger(shortname)

    # no logging of libs

    logger.propagate = False

    if log_level == "debug":
        fmt = "%(asctime)s %(name)-12s %(levelname)-8s %(message)s"

        datefmt = "%Y-%m-%d %H:%M:%S%z"
    else:
        fmt = "%(asctime)s %(message)s"

        datefmt = "%H:%M:%S"

    fs = {
        "asctime": {"color": "green"},
        "hostname": {"color": "magenta"},
        "levelname": {"color": "red", "bold": True},
        "name": {"color": "magenta"},
        "programname": {"color": "cyan"},
        "username": {"color": "yellow"},
    }

    ls = {
        "critical": {"color": "red", "bold": True},
        "debug": {"color": "green"},
        "error": {"color": "red"},
        "info": {},
        "notice": {"color": "magenta"},
        "spam": {"color": "green", "faint": True},
        "success": {"color": "green", "bold": True},
        "verbose": {"color": "blue"},
        "warning": {"color": "yellow"},
    }

    coloredlogs.install(
        level=log_level,
        logger=logger,
        fmt=fmt,
        datefmt=datefmt,
        level_styles=ls,
        field_styles=fs,
    )

    return logger


def json_preview(response, num_lines=5):
    """
    Serialize response to a JSON formatted preview string with num_lines lines.

    Args:
        response: Response object. A server's response to an HTTP request.
        num_lines: Number of lines to be shown. Defaults to 5.

    Returns:
        Preview of the JSON formatted response.
    """

    lines = json.dumps(response, indent=2).splitlines()

    head = "\n".join(lines[:num_lines])

    tail = len(lines) - num_lines

    if tail <= 0:
        return f"{head}\n"
    else:
        return f"{head}\n{tail} more lines hidden"


def check_for_update():
    """
    Show current program version and the latest available on the server.
    """

    log = get_colored_logger(__name__)

    installed_version = version("yapytr")

    log.info("You have installed yapytr %s.", installed_version)

    try:
        r = requests.get(
            "https://api.github.com/repos/ExploracuriousAlex/yapytr/tags", timeout=1
        )
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("Could not determine the latest version from the server.")
        return

    status_code = r.status_code

    if status_code != 200:
        log.error("Could not reach server. Status code %s (%s).", status_code, r.reason)
        return

    latest_version = r.json()[0]["name"]

    log.info("The latest yapytr version on the server is %s.", latest_version)

    if parse_version(installed_version) < parse_version(latest_version):
        log.warning("Your yapytr version is outdated.")
    else:
        log.info("Your yapytr version is up to date. ")


def enhanced_input(message, pattern=None, err_msg="Pattern matching failed."):
    """
    Read a string from standard input and validate.

    The string is validated against the given pattern.
    On Ctrl+C the user can continue or quit the program by pressing it again.

    Args:
        message: The string to be prompted.
        pattern: Regex pattern for validation. Defaults to None.
        err_msg: Message in case the validation fails. Defaults to "Pattern matching failed.".

    Returns:
        Validated string.
    """

    quit_on_sigint = False

    while True:
        try:
            input_str = input(message)
        except KeyboardInterrupt:
            print()
            if quit_on_sigint:
                print("Another Ctrl+C detected. Exiting gracefully.")
                exit()

            print("Ctrl+C detected. To quit the program press again.")
            quit_on_sigint = True
            continue
        except EOFError:
            continue

        if pattern is not None:
            regex = re.compile(pattern)
            fullmatch = regex.fullmatch(str(input_str))
            if not fullmatch:
                print(err_msg)
                continue

        break
    return input_str
