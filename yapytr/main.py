"""
Yapytr main module.
"""

#!/usr/bin/env python
import argparse
import time
from pathlib import Path

import shtab

from .account import clean, login, print_information
from .alarms import Alarms
from .details import Details
from .doc_download import DocDownload
from .portfolio import Portfolio
from .utils import export_transactions
from .utils import check_for_update, get_colored_logger


def create_arguments_parser():
    """
    Define the command-line arguments yapytr requires.

    Returns:
        An ArgumentParser object.
    """

    main_parser = argparse.ArgumentParser(
        description="This program provides an alternative "
        + "access to Trade Republic via the console.",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30),
    )

    main_parser.add_argument(
        "-v",
        "--verbosity",
        help="set verbosity level (default: info)",
        choices=["debug", "info", "warning"],
        default="info",
    )

    sub_parsers = main_parser.add_subparsers(
        title="commands",
        dest="command",
    )

    sub_parser_common_login_args = argparse.ArgumentParser(add_help=False)
    sub_parser_common_login_args.add_argument(
        "-n",
        "--phone_no",
        metavar="PHONE",
        help="Trade Repbulic phone number",
    )
    sub_parser_common_login_args.add_argument("-p", "--pin", help="Trade Repbulic PIN")

    sub_parsers.add_parser(
        "account_info",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30),
        parents=[sub_parser_common_login_args],
        help="print account information",
        description="Log in to Trade Republic and print account information.",
    )

    parser_cancel_price_alarm = sub_parsers.add_parser(
        "cancel_price_alarm",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30),
        parents=[sub_parser_common_login_args],
        help="cancel price alarm",
        description="Cancels a specific price alarm by it's id.",
    )
    parser_cancel_price_alarm.add_argument(
        "alarmid",
        help="price alarm id",
        type=str,
    )

    sub_parsers.add_parser(
        "clean",
        help="clean yapytr settings",
        description="Delete the credentials file "
        + "and cookie file as well as the yapytr settings folder.",
    )

    parser_completion = sub_parsers.add_parser(
        "completion",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30),
        help="print shell completion script",
        description="Automatically generate and print shell tab completion script.",
    )
    shtab.add_argument_to(parser_completion, "shell", parent=main_parser)

    parser_details = sub_parsers.add_parser(
        "details",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30),
        parents=[sub_parser_common_login_args],
        help="print details for an ISIN",
        description="Print details for an ISIN.",
    )
    parser_details.add_argument(
        "isin",
        help="ISIN (International Security Identification Number)",
    )

    parser_dl_docs = sub_parsers.add_parser(
        "dl_docs",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30),
        parents=[sub_parser_common_login_args],
        help="download documents",
        description="Download all pdf documents from the timeline and sort them into folders."
        + " Also export account transactions (account_transactions.csv)"
        + " and JSON files with all events (events_with_documents.json and other_events.json",
    )
    parser_dl_docs.add_argument(
        "output", help="output directory", metavar="PATH", type=Path
    )
    parser_dl_docs.add_argument(
        "-f",
        "--format",
        help="define file name format, available variables:"
        + "\tiso_date, time, title, doc_num, subtitle, id",
        metavar="FORMAT_STRING",
        default="{iso_date}{time} {title}{doc_num}",
    )
    parser_dl_docs.add_argument(
        "-l",
        "--last_days",
        help="number of days to consider (0 for all)",
        metavar="DAYS",
        default=0,
        type=int,
    )
    parser_dl_docs.add_argument(
        "-w",
        "--workers",
        help="number of workers for parallel downloading",
        metavar="WORKERS",
        default=8,
        type=int,
    )

    parser_export_transactions = sub_parsers.add_parser(
        "export_transactions",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30),
        help="export transactions for Portfolio Performance",
        description="Create a CSV with the deposits and removals ready for importing "
        + "into Portfolio Performance.",
    )
    parser_export_transactions.add_argument(
        "input",
        help="Input path to JSON (use other_events.json from dl_docs)",
        metavar="INPUT",
        type=Path,
    )
    parser_export_transactions.add_argument(
        "output", help="Output path of CSV file", metavar="OUTPUT", type=Path
    )
    parser_export_transactions.add_argument(
        "-l",
        "--lang",
        help='Two letter language code or "auto" for system language',
        default="auto",
    )

    sub_parsers.add_parser(
        "login",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30),
        parents=[sub_parser_common_login_args],
        help="login to Trade Republic",
        description="Login to Trade Republic. Check if credentials file exists "
        + "else create it. If no parameters are set but are needed then ask for input.",
    )

    sub_parsers.add_parser(
        "print_price_alarms",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30),
        parents=[sub_parser_common_login_args],
        help="print price alarms",
        description="Print overview of set price alarms.",
    )

    sub_parsers.add_parser(
        "portfolio",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30),
        parents=[sub_parser_common_login_args],
        help="print portfolio",
        description="Print the current Trade Republic portfolio.",
    )

    parser_set_price_alarm = sub_parsers.add_parser(
        "set_price_alarm",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30),
        parents=[sub_parser_common_login_args],
        help="set price alarm",
        description="Sets an alert for a specific ISIN at a specific price",
    )
    parser_set_price_alarm.add_argument(
        "isin",
        help="ISIN (International Security Identification Number)",
        type=str,
    )
    parser_set_price_alarm.add_argument("price", help="target price", type=float)

    sub_parsers.add_parser(
        "version",
        help="print yapytr version",
        description="Print the current version of yapytr.",
    )

    return main_parser


def main():
    """
    Yapytr main() function.

    Take care of user interaction and flow control of the program.
    """
    parser = create_arguments_parser()
    args = parser.parse_args()
    log = get_colored_logger(__name__, args.verbosity)
    log.setLevel(args.verbosity.upper())
    log.debug("logging is set to debug")
    if args.command == "login":
        login(phone_no=args.phone_no, pin=args.pin)
    elif args.command == "dl_docs":
        if args.last_days == 0:
            since_timestamp = 0
        else:
            since_timestamp = (time.time() - (24 * 3600 * args.last_days)) * 1000
        dl = DocDownload(
            login(phone_no=args.phone_no, pin=args.pin),
            args.output,
            args.format,
            since_timestamp=since_timestamp,
            max_workers=args.workers,
        )
        dl.download()
    elif args.command == "account_info":
        print_information(login(phone_no=args.phone_no, pin=args.pin))
    elif args.command == "set_price_alarm":
        tra = login(phone_no=args.phone_no, pin=args.pin)
        alarms = Alarms(tra)
        alarms.set_alarm(args.isin, args.price)
    elif args.command == "cancel_price_alarm":
        tra = login(phone_no=args.phone_no, pin=args.pin)
        alarms = Alarms(tra)
        alarms.cancel_alarm(args.alarmid)
    elif args.command == "print_price_alarms":
        tra = login(phone_no=args.phone_no, pin=args.pin)
        alarms = Alarms(tra)
        alarms.get_alarms()
        alarms.print_alarms()
    elif args.command == "details":
        tra = login(phone_no=args.phone_no, pin=args.pin)
        details = Details(tra)
        details.get_details(args.isin)
        details.print_details()
    elif args.command == "portfolio":
        tra = login(phone_no=args.phone_no, pin=args.pin)
        portfolio = Portfolio(tra)
        portfolio.get_portfolio()
        portfolio.print_portfolio()
    elif args.command == "export_transactions":
        export_transactions(args.input, args.output, args.lang)
    elif args.command == "version":
        check_for_update()
    elif args.command == "clean":
        clean()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
