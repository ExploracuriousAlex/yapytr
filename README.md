# yapytr: Yet another **Py**thon **T**rade **R**epublic program use Trade Republic via the console

This program provides an alternative access to Trade Republic via the console.
It bases on [pytr](https://github.com/marzzzello/pytr) from marzzzello.

It is a refactored version of pytr after I got better acquainted with how pytr works and how Python works in general. The rewrite is mainly about fixing pylint warnings, rewriting docstrings and renaming variables, classes, functions and modules for better understanding.

Neither is it endorsed by Trade Republic nor am I in any relationship with Trade Republic (Trade Republic Bank GmbH).

Use at your own risk!


## Installation

Clone the repo and install e.g. with pip:

```sh
git clone https://github.com/ExploracuriousAlex/yapytr.git
cd yapytr
pip install .
```

## Usage

```
$ yapytr help
usage: yapytr [-h] [-v {debug,info,warning}] {login,dl_docs,portfolio,details,version,get_price_alarms,set_price_alarms,export_transactions,completion,clean} ...

This program provides an alternative access to Trade Republic via the console.

options:
  -h, --help                  show this help message and exit
  -v {debug,info,warning}, --verbosity {debug,info,warning}
                              Set verbosity level (default: info)

commands:
  {account_info,clean,completion,details,dl_docs,export_transactions,login,portfolio,set_price_alarms,show_price_alarms,version}
    account_info              show account information
    clean                     clean yapytr settings
    completion                show shell completion script
    details                   show details for an ISIN
    dl_docs                   download documents
    export_transactions       export transactions for Portfolio Performance
    login                     login to Trade Republic
    portfolio                 show portfolio
    set_price_alarms          set price alarms
    show_price_alarms         show price alarms
    version                   show yapytr version
```

## Authentication

Yapytr uses the same login method as [app.traderepublic.com](https://app.traderepublic.com/), meaning you receive a token in the TradeRepublic app or via SMS.

```sh
$ yapytr login
$ # or
$ yapytr login --phone_no +49123456789 --pin 1234
```

If no arguments are supplied yapytr will look for them in the file `~/.yapytr/credentials` (the first line must contain the phone number, the second line the pin). If the file doesn't exist yapytr will ask for for the phone number and pin.
