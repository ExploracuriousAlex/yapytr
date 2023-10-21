# pytr: use Trade Republic via the console

This program provides an alternative access to Trade Republich via the console.

Neither is it endorsed by Trade Republic nor am I in any relationship with Trade Republic (Trade Republic Bank GmbH).

Use at your own risk!


## Installation

Install with `pip install pytr`

Or you can clone the repo like so:

```sh
git clone https://github.com/ExploracuriousAlex/pytr.git
cd pytr
pip install .
```

## Usage

```
$ pytr help
usage: pytr [-h] [-v {warning,info,debug}] [-V]
            {help,login,dl_docs,portfolio,details,get_price_alarms,set_price_alarms,export_transactions,completion}
            ...

Use "pytr command_name --help" to get detailed help to a specific command

Commands:
  {help,login,dl_docs,portfolio,details,get_price_alarms,set_price_alarms,export_transactions,completion}
                         Desired action to perform
    help                 Print this help message
    login                Check if credentials file exists. If not create it
                         and ask for input. Try to login. Ask for device reset
                         if needed
    dl_docs              Download all pdf documents from the timeline and sort
                         them into folders. Also export account transactions
                         (account_transactions.csv) and JSON files with all
                         events (events_with_documents.json and
                         other_events.json
    portfolio            Show current portfolio
    details              Get details for an ISIN
    get_price_alarms     Get overview of current price alarms
    set_price_alarms     Set price alarms based on diff from current price
    export_transactions  Create a CSV with the deposits and removals ready for
                         importing into Portfolio Performance
    completion           Print shell tab completion

Options:
  -h, --help             show this help message and exit
  -v {warning,info,debug}, --verbosity {warning,info,debug}
                         Set verbosity level (default: info)
  -V, --version          Print version information and quit

```

## Authentication

Pytr uses the same login method as [app.traderepublic.com](https://app.traderepublic.com/), meaning you receive a token in the TradeRepublic app or via SMS.

```sh
$ pytr login
$ # or
$ pytr login --phone_no +49123456789 --pin 1234
```

If no arguments are supplied pytr will look for them in the file `~/.pytr/credentials` (the first line must contain the phone number, the second line the pin). If the file doesn't exist pytr will ask for for the phone number and pin.
