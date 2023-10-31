"""
Module providing the Portfolio class for checking the Trade Republic portfolio.
"""
import asyncio
from .utils import json_preview, get_colored_logger


class Portfolio:
    """
    Class for checking the Trade Republic portfolio.
    """

    def __init__(self, tr_api):
        self.log = get_colored_logger(__name__)
        self.tr_api = tr_api
        self.compact_portfolio = None
        self.cash = None

    async def portfolio_loop(self):
        """
        Requests portfolio and cash information from Trade Republic websocket and
        saves them upon receipt.
        """

        await self.tr_api.compact_portfolio()

        await self.tr_api.cash()

        # await self.tr_api.available_cash_for_payout()

        receiption_status = 0
        flag_compact_portfolio = 1  # 2^0
        flag_cash = 2  # 2^1

        desired_receiption_status = 0
        desired_receiption_status |= flag_compact_portfolio
        desired_receiption_status |= flag_cash

        while receiption_status != desired_receiption_status:
            subscription_id, subscription, response = await self.tr_api.recv()

            if subscription["type"] == "compactPortfolio":
                receiption_status |= flag_compact_portfolio
                self.compact_portfolio = response

            elif subscription["type"] == "cash":
                receiption_status |= flag_cash
                self.cash = response

            # elif subscription['type'] == 'availableCashForPayout':
            #     recv += 1
            #     self.payoutCash = response

            else:
                self.log.debug(
                    "unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response),
                )

            await self.tr_api.unsubscribe(subscription_id)

        # Populate netValue for each ISIN
        positions = self.compact_portfolio["positions"]
        subscriptions = {}
        for (
            pos
        ) in positions:  # sorted(positions, key=lambda x: x["netSize"], reverse=True):
            isin = pos["instrumentId"]
            # subscription_id = await self.tr.instrument_details(pos['instrumentId'])
            subscription_id = await self.tr_api.ticker(isin, exchange="LSX")
            subscriptions[subscription_id] = pos

        while len(subscriptions) > 0:
            subscription_id, subscription, response = await self.tr_api.recv()

            if subscription["type"] == "ticker":
                await self.tr_api.unsubscribe(subscription_id)
                pos = subscriptions[subscription_id]
                subscriptions.pop(subscription_id, None)
                pos["netValue"] = float(response["last"]["price"]) * float(
                    pos["netSize"]
                )
            else:
                self.log.debug(
                    "unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response),
                )

        # Populate name for each ISIN
        subscriptions = {}
        for (
            pos
        ) in positions:  # sorted(positions, key=lambda x: x["netSize"], reverse=True):
            isin = pos["instrumentId"]
            subscription_id = await self.tr_api.instrument_details(pos["instrumentId"])
            subscriptions[subscription_id] = pos

        while len(subscriptions) > 0:
            subscription_id, subscription, response = await self.tr_api.recv()

            if subscription["type"] == "instrument":
                await self.tr_api.unsubscribe(subscription_id)
                pos = subscriptions[subscription_id]
                subscriptions.pop(subscription_id, None)
                pos["name"] = response["shortName"]
            else:
                self.log.debug(
                    "unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response),
                )

    def print_portfolio(self):
        """
        Print the portfolio.
        """

        # self.log.debug(self.compact_portfolio)

        print(
            "Name                      ISIN            avgCost * "
            + "  quantity =    buyCost ->   netValue       diff   %-diff"
        )
        print(
            "------------------------- ------------ ----------   "
            + "----------   ----------    ---------- ---------- -------"
        )
        total_buy_cost = 0.0
        total_net_value = 0.0
        positions = self.compact_portfolio["positions"]
        for pos in sorted(positions, key=lambda x: float(x["netSize"]), reverse=True):
            buy_cost = float(pos["averageBuyIn"]) * float(pos["netSize"])
            diff = float(pos["netValue"]) - buy_cost
            if buy_cost == 0:
                diff_in_percent = 0.0
            else:
                diff_in_percent = ((pos["netValue"] / buy_cost) - 1) * 100
            total_buy_cost += buy_cost
            total_net_value += float(pos["netValue"])

            print(
                f"{pos['name']:<25.25} {pos['instrumentId']:>12} "
                + f"{float(pos['averageBuyIn']):>10.2f} * {float(pos['netSize']):>10.2f}"
                + f" = {float(buy_cost):>10.2f} -> {float(pos['netValue']):>10.2f} "
                + f"{diff:>10.2f} {diff_in_percent:>7.1f}%"
            )

        print(
            "------------------------- ------------ ----------   "
            + "----------   ----------    ---------- ---------- -------"
        )
        print(
            "Name                      ISIN            avgCost * "
            + "  quantity =    buyCost ->   netValue       diff   %-diff"
        )
        print()

        diff = total_net_value - total_buy_cost
        if total_buy_cost == 0:
            diff_in_percent = 0.0
        else:
            diff_in_percent = ((total_net_value / total_buy_cost) - 1) * 100
        print(
            f"Depot {total_buy_cost:>43.2f} -> {total_net_value:>10.2f} "
            + f"{diff:>10.2f} {diff_in_percent:>7.1f}%"
        )

        cash = float(self.cash[0]["amount"])
        currency = self.cash[0]["currencyId"]
        print(f"Cash {currency} {cash:>40.2f} -> {cash:>10.2f}")
        print(f"Total {cash+total_buy_cost:>43.2f} -> {cash+total_net_value:>10.2f}")

    def get(self):
        """
        Executes the query of portfolio and cash information asynchronously until it is finished.

        Triggers the data to be output when ready.
        """
        asyncio.get_event_loop().run_until_complete(self.portfolio_loop())

        self.print_portfolio()
