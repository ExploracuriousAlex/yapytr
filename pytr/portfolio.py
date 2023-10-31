import asyncio
from .utils import json_preview, get_colored_logger


class Portfolio:
    def __init__(self, tr_api):
        self.tr_api = tr_api
        self.portfolio = None
        self.cash = None
        

    async def portfolio_loop(self):
        recv = 0

        await self.tr_api.portfolio()

        await self.tr_api.cash()

        # await self.tr_api.available_cash_for_payout()

        while True:
            _subscription_id, subscription, response = await self.tr_api.recv()

            if subscription["type"] == "compactPortfolio":
                recv += 1
                self.portfolio = response

            elif subscription["type"] == "cash":
                recv += 1

                self.cash = response

            # elif subscription['type'] == 'availableCashForPayout':

            #     recv += 1

            #     self.payoutCash = response
            else:
                print(
                    f"unmatched subscription of type '{subscription['type']}':\n{json_preview(response)}"
                )

            if recv == 2:
                return

    def print_portfolio(self):
        """
        Print the portfolio.
        """        

        log = get_colored_logger(__name__)

        log.debug(self.portfolio)

        print()

        print(
            f"{"ISIN".ljust(12)}  {"quantity".rjust(12)}  {"avg. buying price".rjust(20)}  {"total buying costs".rjust(20)}"
        )

        positions = self.portfolio["positions"]

        for pos in sorted(positions, key=lambda x: float(x["netSize"]), reverse=True):
            
            net_size = float(pos["netSize"])
            average_buy_in = float(pos["averageBuyIn"])

            buy_costs = net_size * average_buy_in

            print(
                f"{pos['instrumentId']:<12}  {net_size:>12.2f}  {average_buy_in:>20.2f}  {buy_costs:>20.2f}"
            )

        print()

        cash_amount = float(self.cash[0]["amount"])
        currency = self.cash[0]["currencyId"]

        print(f"Cash:{cash_amount:>12.2f} {currency}")

        print()

    def get(self):
        asyncio.get_event_loop().run_until_complete(self.portfolio_loop())

        self.print_portfolio()
