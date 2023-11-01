"""
A Portfolio class.
"""
import asyncio
from .utils import json_preview, get_colored_logger


class Portfolio:
    """
    Class to receive and print the Trade Republic portfolio.
    """

    def __init__(self, tr_api):
        """Initializes the instance.

        Args:
          tr_api: The `TradeRepublicApi` object to be used to interact with Trade Republic.
        """
        self._log = get_colored_logger(__name__)
        self._tr_api = tr_api
        self._compact_portfolio = None
        self._cash = None

    async def _portfolio_loop(self):
        """
        Receive portfolio.

        Subscribe to compactPortfolio and cash information from Trade Republic websocket.
        Save it in the `Portfolio` object upon receipt and unsubscribe.
        Also subscribe to ticker andd instrument information from Trade Republic websocket for positions in the portfolio to receive name and last price (from LSX).
        """

        await self._tr_api.compact_portfolio()
        await self._tr_api.cash()

        # define flags to control the loop
        flag_compact_portfolio = 1  # 2^0
        flag_cash = 2  # 2^1

        receiption_status = 0

        desired_receiption_status = 0
        desired_receiption_status |= flag_compact_portfolio
        desired_receiption_status |= flag_cash

        while receiption_status != desired_receiption_status:
            subscription_id, subscription, response = await self._tr_api.recv()

            if subscription["type"] == "compactPortfolio":
                receiption_status |= flag_compact_portfolio
                self._compact_portfolio = response

            elif subscription["type"] == "cash":
                receiption_status |= flag_cash
                self._cash = response

            else:
                self._log.debug(
                    "unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response),
                )

            await self._tr_api.unsubscribe(subscription_id)

        # Populate netValue for each ISIN
        positions = self._compact_portfolio["positions"]
        subscriptions = {}
        for (
            pos
        ) in positions:  # sorted(positions, key=lambda x: x["netSize"], reverse=True):
            isin = pos["instrumentId"]
            # subscription_id = await self.tr.instrument_details(pos['instrumentId'])
            subscription_id = await self._tr_api.ticker(isin, exchange="LSX")
            subscriptions[subscription_id] = pos

        while len(subscriptions) > 0:
            subscription_id, subscription, response = await self._tr_api.recv()

            if subscription["type"] == "ticker":
                await self._tr_api.unsubscribe(subscription_id)
                pos = subscriptions[subscription_id]
                subscriptions.pop(subscription_id, None)
                pos["netValue"] = float(response["last"]["price"]) * float(
                    pos["netSize"]
                )
            else:
                self._log.debug(
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
            subscription_id = await self._tr_api.instrument_details(pos["instrumentId"])
            subscriptions[subscription_id] = pos

        while len(subscriptions) > 0:
            subscription_id, subscription, response = await self._tr_api.recv()

            if subscription["type"] == "instrument":
                await self._tr_api.unsubscribe(subscription_id)
                pos = subscriptions[subscription_id]
                subscriptions.pop(subscription_id, None)
                pos["name"] = response["shortName"]
            else:
                self._log.debug(
                    "unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response),
                )

    def print_portfolio(self):
        """
        Print the portfolio.

        Print portfolio and cash information to the standard output stream.
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
        positions = self._compact_portfolio["positions"]
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

        cash = float(self._cash[0]["amount"])
        currency = self._cash[0]["currencyId"]
        print(f"Cash {currency} {cash:>40.2f} -> {cash:>10.2f}")
        print(f"Total {cash+total_buy_cost:>43.2f} -> {cash+total_net_value:>10.2f}")

    def get_portfolio(self):
        """
        Execute the data receiving loop to receive the portfolio.

        The received data can be printed with `print_portfolio` method.
        """
        asyncio.get_event_loop().run_until_complete(self._portfolio_loop())
