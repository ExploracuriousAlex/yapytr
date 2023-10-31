"""
Module providing the Alarms class for Trade Republic price alarm handling.
"""
import asyncio
from datetime import datetime

from yapytr.utils import json_preview


class Alarms:
    """
    Class for handling Trade Republic price alarms.
    """

    def __init__(self, tr_api):
        self.tr_api = tr_api
        self.alarms = None

    async def alarms_loop(self):
        """
        Requests price alerts from Trade Republic websocket and saves them upon receipt.
        """
        recv = 0

        await self.tr_api.price_alarm_overview()

        while True:
            _subscription_id, subscription, response = await self.tr_api.recv()

            if subscription["type"] == "priceAlarms":
                recv += 1
                self.alarms = response
            else:
                print(
                    f"unmatched subscription of type '{subscription['type']}'"
                    + f":\n{json_preview(response)}"
                )

            if recv == 1:
                return

    def overview(self):
        """
        Print the stored price alarms.
        """
        print("ISIN         status created  target diff% createdAt        triggeredAT")
        for a in self.alarms:
            ts = int(a["createdAt"]) / 1000.0

            created = datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="minutes")

            if a["triggeredAt"] is None:
                triggered = "-"
            else:
                ts = int(a["triggeredAt"]) / 1000.0

                triggered = datetime.fromtimestamp(ts).isoformat(
                    sep=" ", timespec="minutes"
                )

            if a["createdPrice"] == 0:
                price_difference = 0.0
            else:
                price_difference = (
                    float(a["targetPrice"]) / float(a["createdPrice"])
                ) * 100 - 100

            print(
                f"{a['instrumentId']} {a['status']} {float(a['createdPrice']):>7.2f} "
                + f"{float(a['targetPrice']):>7.2f} "
                + f"{price_difference:>5.1f} {created} {triggered}"
            )

    def get(self):
        """
        Executes the query of price alarms asynchronously until it is finished.

        Triggers the data to be output when ready.
        """
        asyncio.get_event_loop().run_until_complete(self.alarms_loop())

        self.overview()
