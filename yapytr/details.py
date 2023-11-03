"""
A Details class.
"""
import asyncio
from datetime import datetime, timedelta

from .utils import json_preview, get_colored_logger

UNDERLINE = "\033[4m"
BLUE = "\033[94m"
RST_FORMAT = "\033[0m"


class Details:
    """
    Class to receive and print details for an ISIN from Trade Republic.
    """

    def __init__(self, tr_api):
        """
        Initializes the instance.

        Args:
            tr_api: The `TradeRepublicApi` object to be used to interact with Trade Republic.
            isin: ISIN (International Security Identification Number)
        """
        self._log = get_colored_logger(__name__)
        self._tr_api = tr_api
        self._stock_details = None
        self._neon_news = None
        self._ticker = None
        self._performance = None
        self._instrument = None
        self._instrument_suitability = None

    async def _get_details_loop(self, isin):
        await self._tr_api.stock_details(isin)
        await self._tr_api.news(isin)
        # await self._tr_api.ticker(isin, exchange="LSX")
        # await self._tr_api.performance(isin, exchange="LSX")
        await self._tr_api.instrument_details(isin)
        # await self._tr_api.instrument_suitability(isin)

        # define flags to control the loop
        flag_stock_details_received = 1  # 2^0
        flag_neon_news_received = 2  # 2^1
        flag_ticker_received = 4  # 2^2
        flag_performance_received = 8  # 2^3
        flag_instrument_received = 16  # 2^4
        flag_instrument_suitability_received = 32  # 2^5

        receiption_status = 0

        desired_receiption_status = 0
        desired_receiption_status |= flag_stock_details_received
        desired_receiption_status |= flag_neon_news_received
        # desired_receiption_status |= flag_ticker_received
        # desired_receiption_status |= flag_performance_received
        desired_receiption_status |= flag_instrument_received
        # desired_receiption_status |= flag_instrument_suitability_received

        while receiption_status != desired_receiption_status:
            subscription_id, subscription, response = await self._tr_api.recv()

            if subscription["type"] == "stockDetails":
                receiption_status |= flag_stock_details_received
                self._stock_details = response

            elif subscription["type"] == "neonNews":
                receiption_status |= flag_neon_news_received
                self._neon_news = response

            elif subscription["type"] == "ticker":
                receiption_status |= flag_ticker_received
                self._ticker = response

            elif subscription["type"] == "performance":
                receiption_status |= flag_performance_received
                self._performance = response

            elif subscription["type"] == "instrument":
                receiption_status |= flag_instrument_received
                self._instrument = response

            elif subscription["type"] == "instrumentSuitability":
                receiption_status |= flag_instrument_suitability_received
                self._instrument_suitability = response

            else:
                self._log.debug(
                    "Unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response, num_lines=30),
                )

            await self._tr_api.unsubscribe(subscription_id)

    def _print_instrument(self):
        print()
        print(f"{UNDERLINE}Basic information:{RST_FORMAT}")
        print(f"{f"{BLUE}name:{RST_FORMAT}":<30} {self._instrument["name"]}")
        print(f"{f"{BLUE}shortName:{RST_FORMAT}":<30} {self._instrument["shortName"]}")
        print(f"{f"{BLUE}typeId:{RST_FORMAT}":<30} {self._instrument["typeId"]}")

        print()
        print(f"{UNDERLINE}Trading on the following exchanges:{RST_FORMAT}")
        for ex in self._instrument["exchanges"]:
            print(f"{f"{BLUE}{ex['slug']}:{RST_FORMAT}":<30} {ex['nameAtExchange']} ({ex['symbolAtExchange']})")

        print()
        print(f"{UNDERLINE}Tags:{RST_FORMAT}")
        for tag in self._instrument["tags"]:
            print(f"{f"{BLUE}{tag['type']}:{RST_FORMAT}":<30} {tag['name']}")

        print()

    def _print_stock_details(self):
        company = self._stock_details["company"]

        print()
        print(f"{UNDERLINE}Detailed information:{RST_FORMAT}")
        for company_detail in company:
            if company[company_detail] is not None:
                print(f"{f"{BLUE}{company_detail}:{RST_FORMAT}":<30} {company[company_detail]}")

        print()

        # for detail in self._stock_details:
        #     if (
        #         detail != "company"
        #         and self._stock_details[detail] is not None
        #         and self._stock_details[detail] != []
        #     ):
        #         print(f"{detail:15}: {self._stock_details[detail]}")

    def _print_news(self, relevant_days=30):
        since = datetime.now() - timedelta(days=relevant_days)

        print()
        print(f"{UNDERLINE}News:{RST_FORMAT}")
        for news in self._neon_news:
            newsdate = datetime.fromtimestamp(news["createdAt"] / 1000.0)

            if newsdate > since:
                dateiso = newsdate.isoformat(sep=" ", timespec="minutes")
                print(f"{f"{BLUE}{dateiso}:{RST_FORMAT}":<30} {news['headline']}")

    def print_details(self):
        """
        Print details.

        Print received details for an ISIN to the standard output stream.
        Use `get_details(isin)` to receive the details upfront.
        """
        self._print_instrument()
        self._print_news()
        self._print_stock_details()

    def get_details(self, isin):
        """
        Execute the data receiving loop to receive details for an ISIN.

        The received data can be printed with `print_details` method.

        Args:
            isin: ISIN (International Security Identification Number)
        """
        asyncio.get_event_loop().run_until_complete(self._get_details_loop(isin))
