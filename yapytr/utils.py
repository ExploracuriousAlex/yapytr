"""
Helper functions for yapytr.
"""

import json
import logging
import re
import sys
from datetime import datetime
from importlib.metadata import version
from locale import getlocale

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
    Preview JSON.

    Serialize response to a JSON formatted preview string with maximum `num_lines` lines.

    Args:
        response: Response object. A server's response to an HTTP request.
        num_lines: Maximum number of lines of the preview string. Defaults to 5.

    Returns:
        Preview of the JSON formatted response.
    """

    lines = json.dumps(response, indent=2).splitlines()

    head = "\n".join(lines[:num_lines])

    tail = len(lines) - num_lines

    if tail <= 0:
        return f"{head}\n"

    return f"{head}\n{tail} more lines hidden"


def check_for_update():
    """
    Print current program version and the latest available on the server.
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
                sys.exit()

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


def export_transactions(input_path, output_path, lang="auto"):
    """
    Export transactions for Portfolio Performance.

    Create a CSV file with the deposits and removals ready for importing into Portfolio Performance.

    Args:
        input_path: Path of a JSON file containing timeline events.
        output_path: Target path of the CSV file to be written.
        lang: Language of the created file. Defaults to "auto".
    """

    log = get_colored_logger(__name__)

    if lang == "auto":
        locale = getlocale()[0]

        if locale is None:
            lang = "en"

        else:
            lang = locale.split("_")[0]

    if lang not in ["cs", "de", "en", "es", "fr", "it", "nl", "pt", "ru"]:
        lang = "en"

    # i18n source from Portfolio Performance:
    # https://github.com/portfolio-performance/portfolio/blob/master/name.abuchen.portfolio/src/name/abuchen/portfolio/messages_de.properties
    # https://github.com/portfolio-performance/portfolio/blob/master/name.abuchen.portfolio/src/name/abuchen/portfolio/model/labels_de.properties

    i18n = {
        "date": {
            "cs": "Datum",
            "de": "Datum",
            "en": "Date",
            "es": "Fecha",
            "fr": "Date",
            "it": "Data",
            "nl": "Datum",
            "pt": "Data",
            "ru": "\u0414\u0430\u0442\u0430",
        },
        "type": {
            "cs": "Typ",
            "de": "Typ",
            "en": "Type",
            "es": "Tipo",
            "fr": "Type",
            "it": "Tipo",
            "nl": "Type",
            "pt": "Tipo",
            "ru": "\u0422\u0438\u043F",
        },
        "value": {
            "cs": "Hodnota",
            "de": "Wert",
            "en": "Value",
            "es": "Valor",
            "fr": "Valeur",
            "it": "Valore",
            "nl": "Waarde",
            "pt": "Valor",
            "ru": "\u0417\u043D\u0430\u0447\u0435\u043D\u0438\u0435",
        },
        "deposit": {
            "cs": "Vklad",
            "de": "Einlage",
            "en": "Deposit",
            "es": "Dep\u00F3sito",
            "fr": "D\u00E9p\u00F4t",
            "it": "Deposito",
            "nl": "Storting",
            "pt": "Dep\u00F3sito",
            "ru": "\u041F\u043E\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u0435",
        },
        "removal": {
            "cs": "V\u00FDb\u011Br",
            "de": "Entnahme",
            "en": "Removal",
            "es": "Removal",
            "fr": "Retrait",
            "it": "Prelievo",
            "nl": "Opname",
            "pt": "Levantamento",
            "ru": "\u0421\u043F\u0438\u0441\u0430\u043D\u0438\u0435",
        },
    }

    # Read relevant deposit timeline entries

    with open(input_path, encoding="utf-8") as f:
        timeline = json.load(f)

    # Write deposit_transactions.csv file

    # date, transaction, shares, amount, total, fee, isin, name

    log.info("Write deposit entries")

    with open(output_path, "w", encoding="utf-8") as f:
        # f.write('Datum;Typ;Stück;amount;Wert;Gebühren;ISIN;name\n')

        csv_fmt = "{date};{type};{value}\n"

        header = csv_fmt.format(
            date=i18n["date"][lang], type=i18n["type"][lang], value=i18n["value"][lang]
        )

        f.write(header)

        for event in timeline:
            event = event["data"]

            date_time = datetime.fromtimestamp(int(event["timestamp"] / 1000))

            date = date_time.strftime("%Y-%m-%d")

            title = event["title"]

            try:
                body = event["body"]

            except KeyError:
                body = ""

            if "storniert" in body:
                continue

            # Cash in

            if title in ["Einzahlung", "Bonuszahlung"]:
                f.write(
                    csv_fmt.format(
                        date=date,
                        type=i18n["deposit"][lang],
                        value=event["cashChangeAmount"],
                    )
                )

            elif title == "Auszahlung":
                f.write(
                    csv_fmt.format(
                        date=date,
                        type=i18n["removal"][lang],
                        value=abs(event["cashChangeAmount"]),
                    )
                )

            # Dividend - Shares

            elif title == "Reinvestierung":
                # TODO: implement reinvestment export

                log.warning("Detected reinvestment, skipping... (not implemented yet)")

    log.info("Deposit creation finished!")
