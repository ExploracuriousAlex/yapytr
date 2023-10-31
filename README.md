# pytr: use Trade Republic via the console

This program provides an alternative access to Trade Republic via the console.

Neither is it endorsed by Trade Republic nor am I in any relationship with Trade Republic (Trade Republic Bank GmbH).

Use at your own risk!


## Installation

Clone the repo and install e.g. with pip:

```sh
git clone https://github.com/ExploracuriousAlex/pytr.git
cd pytr
pip install .
```

## Usage

```
$ pytr help
usage: pytr [-h] [-v {debug,info,warning}] {login,dl_docs,portfolio,details,version,get_price_alarms,set_price_alarms,export_transactions,completion,clean} ...

This program provides an alternative access to Trade Republic via the console.

options:
  -h, --help                  show this help message and exit
  -v {debug,info,warning}, --verbosity {debug,info,warning}
                              Set verbosity level (default: info)

commands:
  {account_info,clean,completion,details,dl_docs,export_transactions,login,portfolio,set_price_alarms,show_price_alarms,version}
    account_info              show account information
    clean                     clean pytr settings
    completion                show shell completion script
    details                   show details for an ISIN
    dl_docs                   download documents
    export_transactions       export transactions for Portfolio Performance
    login                     login to Trade Republic
    portfolio                 show portfolio
    set_price_alarms          set price alarms
    show_price_alarms         show price alarms
    version                   show pytr version
```

## Authentication

Pytr uses the same login method as [app.traderepublic.com](https://app.traderepublic.com/), meaning you receive a token in the TradeRepublic app or via SMS.

```sh
$ pytr login
$ # or
$ pytr login --phone_no +49123456789 --pin 1234
```

If no arguments are supplied pytr will look for them in the file `~/.pytr/credentials` (the first line must contain the phone number, the second line the pin). If the file doesn't exist pytr will ask for for the phone number and pin.
