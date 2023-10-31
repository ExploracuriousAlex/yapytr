import asyncio
from datetime import datetime, timedelta

from .utils import json_preview


class Details:
    def __init__(self, tr_api, isin):
        self.tr_api = tr_api
        self.isin = isin
        self.stockDetails = None
        self.neonNews = None
        self.ticker = None
        self.performance = None
        self.instrument = None
        self.instrumentSuitability = None

    async def details_loop(self):
        recv = 0

        await self.tr_api.stock_details(self.isin)

        await self.tr_api.news(self.isin)

        # await self.tr_api.subscribe_news(self.isin)

        await self.tr_api.ticker(self.isin, exchange="LSX")

        await self.tr_api.performance(self.isin, exchange="LSX")

        await self.tr_api.instrument_details(self.isin)

        await self.tr_api.instrument_suitability(self.isin)

        # await self.tr_api.add_watchlist(self.isin)

        # await self.tr_api.remove_watchlist(self.isin)

        # await self.tr_api.savings_plan_parameters(self.isin)

        # await self.tr_api.unsubscribe_news(self.isin)

        while True:
            _subscription_id, subscription, response = await self.tr_api.recv()

            if subscription["type"] == "stockDetails":
                recv += 1

                self.stockDetails = response

            elif subscription["type"] == "neonNews":
                recv += 1

                self.neonNews = response

            elif subscription["type"] == "ticker":
                recv += 1

                self.ticker = response

            elif subscription["type"] == "performance":
                recv += 1
                self.performance = response

            elif subscription["type"] == "instrument":
                recv += 1
                self.instrument = response

            elif subscription["type"] == "instrumentSuitability":
                recv += 1

                self.instrumentSuitability = response

                print("instrumentSuitability:", response)
            else:
                print(
                    f"unmatched subscription of type '{subscription['type']}':\n{json_preview(response, num_lines=30)}"
                )

            if recv == 6:
                return

    def print_instrument(self):
        print("Name:", self.instrument["name"])

        print("ShortName:", self.instrument["shortName"])

        print("Type:", self.instrument["typeId"])

        for ex in self.instrument["exchanges"]:
            print(f"{ex['slug']}: {ex['symbolAtExchange']} {ex['nameAtExchange']}")

        for tag in self.instrument["tags"]:
            print(f"{tag['type']}: {tag['name']}")

    def stock_details(self):
        company = self.stockDetails["company"]

        for company_detail in company:
            if company[company_detail] is not None:
                print(f"{company_detail:15}: {company[company_detail]}")

        for detail in self.stockDetails:
            if (
                detail != "company"
                and self.stockDetails[detail] is not None
                and self.stockDetails[detail] != []
            ):
                print(f"{detail:15}: {self.stockDetails[detail]}")

    def news(self, relevant_days=30):
        since = datetime.now() - timedelta(days=relevant_days)

        for news in self.neonNews:
            newsdate = datetime.fromtimestamp(news["createdAt"] / 1000.0)

            if newsdate > since:
                dateiso = newsdate.isoformat(sep=" ", timespec="minutes")

                print(f"{dateiso}: {news['headline']}")

    def overview(self):
        self.print_instrument()

        self.news()

        self.stock_details()

    def get(self):
        asyncio.get_event_loop().run_until_complete(self.details_loop())

        self.overview()