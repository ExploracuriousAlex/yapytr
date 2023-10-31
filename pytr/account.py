"""
Module provoding the login logic for the Trade Republic account.
"""
import json
import sys
import time

from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.data import JsonLexer

from .tr_api import BASE_DIR, COOKIES_FILE, CREDENTIALS_FILE, TradeRepublicApi
from .utils import enhanced_input, get_colored_logger


def print_information(tr_api):
    """
    Print Trade Republic account information.

    Args:
        tr_api: A TradeRepublicApi object in logged in state.
    """
    formatted_json = json.dumps(tr_api.settings(), indent=2)
    if sys.stdout.isatty():
        colorful_json = highlight(formatted_json, JsonLexer(), TerminalFormatter())
        print(colorful_json)
    else:
        print(formatted_json)


def login(phone_no=None, pin=None):
    """
    Login to Trade Republic.

    Check if credentials file exists else create it.
    If no parameters are set but are needed then ask for input.

    Args:
        phone_no: Your phone number used for Trade Republic. Defaults to None.
        pin: Your Trade Republic pin. Defaults to None.

    Returns:
        TradeRepublicApi object.
    """

    log = get_colored_logger(__name__)

    save_cookies = True

    if phone_no is None and CREDENTIALS_FILE.is_file():
        log.info("Found credentials file")
        with open(CREDENTIALS_FILE, encoding="utf-8") as f:
            lines = f.readlines()
        phone_no = lines[0].strip()
        pin = lines[1].strip()
        phone_no_masked = phone_no[:-8] + "********"
        pin_masked = len(pin) * "*"
        log.info("Phone: %s PIN: %s", phone_no_masked, pin_masked)
    else:
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if phone_no is None:
            log.info("Credentials file not found")

            phone_no = enhanced_input(
                "Please enter your Trade Repbulic phone number in the format +4912345678: ",
                "\+[0-9]{10,15}",  # pylint: disable=anomalous-backslash-in-string
                "Invalid phone number format!",
            )

        else:
            log.info("Phone number provided as argument")

        if pin is None:
            pin = enhanced_input(
                "Please enter your Trade Repbulic pin: ",
                "[0-9]{4}",
                "Invalid pin format!",
            )

        save = enhanced_input('Save credentials? Type "y" to save credentials: ')

        if save.lower() == "y":
            with open(CREDENTIALS_FILE, mode="w", encoding="utf-8") as f:
                f.writelines([phone_no + "\n", pin + "\n"])

            log.info("Saved credentials in %s", CREDENTIALS_FILE)

        else:
            save_cookies = False
            log.info("Credentials not saved")

    tr_api = TradeRepublicApi(phone_no=phone_no, pin=pin, save_cookies=save_cookies)

    # Use same login as app.traderepublic.com
    if tr_api.resume_websession():
        log.info("Web session resumed")
    else:
        try:
            countdown = tr_api.inititate_weblogin()
        except ValueError as e:
            log.fatal(str(e))
            exit(1)
        request_time = time.time()
        print("Enter the code you received to your mobile app as a notification.")
        print(
            f"Enter nothing if you want to receive the (same) code as SMS. (Countdown: {countdown})"
        )
        code = enhanced_input("Code: ")
        if code == "":
            countdown = countdown - (time.time() - request_time)
            for remaining in range(int(countdown)):
                print(
                    f"Need to wait {int(countdown-remaining)} seconds before requesting SMS...",
                    end="\r",
                )
                time.sleep(1)
            print()
            tr_api.resend_weblogin()
            code = enhanced_input(
                "SMS requested. Enter the confirmation code: ",
                "[0-9]{4}",
                "Invalid code. The Trade Republic verification code consists of 4 digits.",
            )
        tr_api.complete_weblogin(code)

    log.info("Logged in")
    return tr_api


def clean():
    """
    Delete the pytr settings.

    Check whether a credential file and/or cookie file exists and if so, delete it.
    Also delete the pytr settings folder if there is one.
    """
    log = get_colored_logger(__name__)

    if CREDENTIALS_FILE.is_file():
        log.debug("Found credentials file '%s'.", CREDENTIALS_FILE)
        CREDENTIALS_FILE.unlink(missing_ok=True)
        log.info("Deleted credentials file.")
    else:
        log.info("No credentials file found. Nothing to do.")

    if COOKIES_FILE.is_file():
        log.debug("Found cookies file '%s'.", COOKIES_FILE)
        COOKIES_FILE.unlink(missing_ok=True)
        log.info("Deleted cookies file.")
    else:
        log.info("No cookies file found. Nothing to do.")

    if BASE_DIR.is_dir():
        log.debug("Found pytr folder '%s'.", BASE_DIR)
        BASE_DIR.rmdir()
        log.info("Deleted pytr settings folder.")
    else:
        log.info("No settings folder found. Nothing to do.")
